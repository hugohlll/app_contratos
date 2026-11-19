"""OM beneficiada dos contratos da UG no Contratos.gov.br (#51).

A UG 120006 executa os próprios contratos e os das OMs apoiadas, e a API pública não informa a
UASG beneficiada. Este módulo mantém o catálogo (``ContratoCatalogo``) com os contratos da UG,
sugere a OM beneficiada a partir de indícios públicos e aplica a classificação feita pelo
Administrador. Só o contrato classificado como GAP-BR vira ``Contrato`` no SISCONT.

Ver ``docs/contratosgov/mapeamento-campos.md``, seção 9.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from contratos.models import (
    Contrato, ContratoCatalogo, Empresa, OrganizacaoMilitar, RegistroClassificacao,
)
from contratos.services.contratosgov import ContratosGovErro

logger = logging.getLogger('contratos.contratosgov')

TIPO_ACOMPANHADO = 'Contrato'  # Empenho e Outros não entram no catálogo (decisão de 19/11/2026)

# Número formal com a sigla da OM depois de "GAP-BR", ex.: "013/GAP-BR-COMGEP/2024".
RE_NUMERO_FORMAL = re.compile(r'\d{1,5}\s*/\s*GA[PO]\s*-?\s*BR\s*[-–]\s*([A-Z0-9][A-Z0-9\-–]*?)\s*/\s*\d{4}', re.I)
RE_NUMERO = re.compile(r'^\s*0*(\d+)\s*/\s*(\d{4})\s*$')


class ClassificacaoErro(Exception):
    """Classificação inválida ou que não pôde ser aplicada."""


# ---------------------------------------------------------------------------- conversões
def normalizar_numero(numero):
    """'00013/2024' e '013/2024' → (13, 2024). Devolve None fora do padrão número/ano."""
    m = RE_NUMERO.match(numero or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


def numero_local(numero):
    """Número no formato usado no SISCONT ('013/2024')."""
    n = normalizar_numero(numero)
    return f'{n[0]:03d}/{n[1]}' if n else numero


def so_digitos(texto):
    return re.sub(r'\D', '', texto or '')


def valor_br(texto):
    """'4.464.512,73' → Decimal('4464512.73'). Aceita também número JSON."""
    if texto in (None, '', 'null'):
        return None
    if isinstance(texto, (int, float, Decimal)):
        return Decimal(str(texto))
    try:
        return Decimal(str(texto).replace('.', '').replace(',', '.'))
    except InvalidOperation:
        return None


def data_iso(texto):
    try:
        return date.fromisoformat(str(texto)[:10]) if texto and texto != 'null' else None
    except ValueError:
        return None


def _sem_acento(texto):
    return unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()


def _chave(texto):
    """Forma comparável de siglas e nomes: sem acento, sem pontuação, maiúscula."""
    return re.sub(r'[^A-Z0-9]', '', _sem_acento(texto).upper())


# ---------------------------------------------------------------------------- sugestão
@dataclass
class IndiceOMs:
    """Tabelas de busca montadas a partir do cadastro de OMs."""
    por_sigla: dict = field(default_factory=dict)
    por_nome: dict = field(default_factory=dict)
    por_uasg: dict = field(default_factory=dict)
    por_prefixo: list = field(default_factory=list)  # (prefixo, om), do mais longo ao mais curto

    @classmethod
    def carregar(cls):
        indice = cls()
        for om in OrganizacaoMilitar.objects.filter(ativa=True):
            indice.por_sigla[_chave(om.sigla)] = om
            if om.nome:
                indice.por_nome[_chave(om.nome)] = om
            if om.codigo_uasg:
                indice.por_uasg[om.codigo_uasg.strip()] = om
            indice.por_prefixo += [(p, om) for p in om.lista_prefixos_pi()]
        indice.por_prefixo.sort(key=lambda par: -len(par[0]))
        return indice

    def por_texto(self, texto):
        chave = _chave(texto)
        return self.por_sigla.get(chave) or self.por_nome.get(chave)

    def siglas_no_texto(self, texto):
        """OMs cuja sigla (com ou sem hífen) ou nome completo aparece como palavra no texto."""
        encontradas = []
        normal = ' '.join(_sem_acento(texto).upper().split())
        for om in {id(o): o for o in self.por_sigla.values()}.values():
            variantes = {om.sigla.upper(), om.sigla.upper().replace('-', ''), om.sigla.upper().replace('-', ' ')}
            if om.nome:
                variantes.add(' '.join(_sem_acento(om.nome).upper().split()))
            if any(re.search(rf'(?<![A-Z0-9]){re.escape(v)}(?![A-Z0-9])', normal) for v in variantes if v):
                encontradas.append(om)
        return encontradas


def _indicio(fonte, valor, om, observacao=''):
    return {'fonte': fonte, 'valor': valor, 'om': om.sigla if om else '', 'observacao': observacao}


def indicios_da_lista(item, indice):
    """Indícios que vêm na própria lista da UG: unidade requisitante e siglas no objeto."""
    indicios = []
    requisitante = (item.get('unidades_requisitantes') or '').strip()
    if requisitante:
        partes = [p.strip() for p in re.split(r'[;,]', requisitante) if p.strip()] or [requisitante]
        for parte in partes:
            om = indice.por_uasg.get(parte) or indice.por_texto(parte)
            indicios.append(_indicio('Unidade requisitante', parte, om,
                                     '' if om else 'não reconhecida no cadastro de OMs'))
    for om in indice.siglas_no_texto(item.get('objeto')):
        indicios.append(_indicio('Sigla no objeto', om.sigla, om))
    return indicios


def indicios_do_detalhe(cliente, id_contrato, indice):
    """Indícios que exigem consultar o contrato: número formal e plano interno dos empenhos."""
    indicios = []
    textos = []
    for recurso, campo in (('arquivos', 'descricao'), ('historico', 'observacao')):
        for registro in getattr(cliente, recurso)(id_contrato) or []:
            textos.append(registro.get(campo) or '')
    siglas = set()
    for texto in textos:
        for m in RE_NUMERO_FORMAL.finditer(texto):
            siglas.add(m.group(1).upper().replace('–', '-').strip('-'))
    for sigla in sorted(siglas):
        om = indice.por_texto(sigla)
        indicios.append(_indicio('Número formal', f'GAP-BR-{sigla}', om,
                                 '' if om else 'sigla não cadastrada'))

    # Plano interno: o de maior valor empenhado, para não pesar empenhos residuais.
    por_pi = {}
    for emp in cliente.empenhos(id_contrato) or []:
        pi = (emp.get('planointerno') or '').strip()
        if pi:
            por_pi[pi] = por_pi.get(pi, Decimal(0)) + (valor_br(emp.get('empenhado')) or Decimal(0))
    if por_pi:
        pi = max(por_pi, key=por_pi.get)
        codigo = pi.split(' - ')[0].strip().upper()
        om = next((o for prefixo, o in indice.por_prefixo if codigo.startswith(prefixo)), None)
        indicios.append(_indicio('Plano interno', pi[:80], om,
                                 '' if om else 'prefixo sem OM no cadastro'))
    return indicios


def decidir_sugestao(indicios, indice):
    """Sugere a OM só quando todos os indícios reconhecidos apontam para a mesma OM."""
    siglas = {i['om'] for i in indicios if i['om']}
    if len(siglas) != 1:
        return None
    return indice.por_sigla.get(_chave(siglas.pop()))


def atualizar_sugestao(catalogo, item, cliente, indice):
    """Recalcula a sugestão de um contrato pendente. Se a consulta de detalhes falhar, mantém a anterior."""
    indicios = indicios_da_lista(item, indice)
    try:
        indicios += indicios_do_detalhe(cliente, catalogo.id_contratosgov, indice)
    except ContratosGovErro as e:
        logger.warning('Sugestão do contrato %s não atualizada: %s', catalogo.numero, e)
        return False
    catalogo.sugestao_indicios = indicios
    catalogo.sugestao_om = decidir_sugestao(indicios, indice)
    catalogo.sugestao_em = timezone.now()
    catalogo.save(update_fields=['sugestao_indicios', 'sugestao_om', 'sugestao_em'])
    return True


# ---------------------------------------------------------------------------- classificação
def om_gapbr():
    om = OrganizacaoMilitar.objects.filter(eh_gapbr=True).first()
    if om is None:
        raise ClassificacaoErro('Nenhuma OM marcada como GAP-BR no cadastro de OMs.')
    return om


def _registrar(catalogo, usuario, situacao_anterior, om_anterior, justificativa='', automatico=False):
    RegistroClassificacao.objects.create(
        catalogo=catalogo, usuario=usuario, automatico=automatico, justificativa=justificativa,
        situacao_anterior=situacao_anterior, om_anterior=om_anterior.sigla if om_anterior else '',
        situacao_nova=catalogo.situacao, om_nova=catalogo.om_beneficiada.sigla if catalogo.om_beneficiada else '',
    )


def promover(catalogo):
    """Cria (ou reaproveita) o ``Contrato`` do SISCONT para um contrato classificado como GAP-BR."""
    if catalogo.contrato_id:
        return catalogo.contrato
    existente = localizar_no_siscont(catalogo.numero, catalogo.fornecedor_cnpj)
    if existente:
        catalogo.contrato = existente
        return existente
    numero = numero_local(catalogo.numero)
    if Contrato.objects.filter(numero=numero).exists():
        raise ClassificacaoErro(
            f'Já existe no SISCONT o contrato {numero} com outra empresa. Confira o cadastro antes de classificar.')
    if not (catalogo.vigencia_inicio and catalogo.vigencia_fim):
        raise ClassificacaoErro('O Contratos.gov.br não informa a vigência deste contrato.')
    empresa = Empresa.objects.filter(cnpj=catalogo.fornecedor_cnpj).first() or Empresa.objects.create(
        cnpj=catalogo.fornecedor_cnpj[:18], razao_social=catalogo.fornecedor_nome[:200])
    contrato = Contrato.objects.create(
        numero=numero,
        tipo='RECEITA' if catalogo.receita_despesa.lower() == 'receita' else 'DESPESA',
        objeto=catalogo.objeto,
        empresa=empresa,
        vigencia_inicio=catalogo.vigencia_inicio,
        vigencia_fim=catalogo.vigencia_fim,
        valor_total=catalogo.valor_global or Decimal(0),
    )
    catalogo.contrato = contrato
    return contrato


@transaction.atomic
def classificar(catalogo, usuario, om=None, desconsiderar=False, justificativa=''):
    """Aplica a classificação do Administrador. Devolve avisos para exibir na tela.

    Serve também para corrigir um erro de classificação: tudo fica registrado em
    ``RegistroClassificacao``. O ``Contrato`` do SISCONT nunca é excluído.
    """
    justificativa = (justificativa or '').strip()
    if desconsiderar and not justificativa:
        raise ClassificacaoErro('Informe a justificativa para desconsiderar o contrato.')
    if not desconsiderar and om is None:
        raise ClassificacaoErro('Escolha a OM beneficiada.')
    correcao = catalogo.situacao != ContratoCatalogo.PENDENTE
    if correcao and not justificativa:
        raise ClassificacaoErro('Informe a justificativa da correção.')

    anterior_situacao, anterior_om = catalogo.situacao, catalogo.om_beneficiada
    avisos = []
    if desconsiderar:
        catalogo.situacao, catalogo.om_beneficiada = ContratoCatalogo.DESCONSIDERADO, None
    else:
        catalogo.situacao, catalogo.om_beneficiada = ContratoCatalogo.CLASSIFICADO, om

    if catalogo.eh_gapbr:
        promover(catalogo)
    elif catalogo.contrato_id:
        avisos.append(f'O contrato {catalogo.contrato.numero} continua no SISCONT e deixou de ser atualizado '
                      'pelo Contratos.gov.br. Encerre-o manualmente se for o caso.')
        catalogo.contrato = None

    catalogo.justificativa = justificativa
    catalogo.classificado_por = usuario
    catalogo.classificado_em = timezone.now()
    catalogo.vinculo_automatico = False
    catalogo.save()
    _registrar(catalogo, usuario, anterior_situacao, anterior_om, justificativa)
    return avisos


# ---------------------------------------------------------------------------- sincronização
def localizar_no_siscont(numero, cnpj, contratos=None):
    """Contrato do SISCONT com o mesmo número normalizado e o mesmo CNPJ."""
    chave = normalizar_numero(numero)
    if not chave:
        return None
    candidatos = contratos if contratos is not None else Contrato.objects.select_related('empresa')
    for c in candidatos:
        if normalizar_numero(c.numero) == chave and so_digitos(c.empresa.cnpj) == so_digitos(cnpj):
            return c
    return None


def _campos_da_lista(item):
    fornecedor = item.get('fornecedor') or {}
    return dict(
        numero=(item.get('numero') or '')[:30],
        tipo_instrumento=(item.get('tipo') or '')[:50],
        receita_despesa=(item.get('receita_despesa') or '')[:10],
        categoria_contratosgov=(item.get('categoria') or '')[:100],
        fornecedor_nome=(fornecedor.get('nome') or '')[:255],
        fornecedor_cnpj=(fornecedor.get('cnpj_cpf_idgener') or '')[:30],
        objeto=item.get('objeto') or '',
        vigencia_inicio=data_iso(item.get('vigencia_inicio')),
        vigencia_fim=data_iso(item.get('vigencia_fim')),
        valor_global=valor_br(item.get('valor_global')),
        situacao_contratosgov=(item.get('situacao') or '')[:30],
        unidades_requisitantes=(item.get('unidades_requisitantes') or '')[:255],
        processo=(item.get('processo') or '')[:50],
    )


@dataclass
class ResultadoSincronizacao:
    lidos: int = 0
    no_catalogo: int = 0
    novos: list = field(default_factory=list)          # ContratoCatalogo novos a classificar
    vinculados: list = field(default_factory=list)     # vinculados automaticamente como GAP-BR
    sugestoes: int = 0
    sugestoes_falhas: int = 0
    pendentes: int = 0


def sincronizar_catalogo(cliente, hoje=None, sugestoes=True):
    """Atualiza o catálogo com a lista de contratos ativos da UG.

    Se a lista não puder ser lida, levanta ``ContratosGovErro`` antes de qualquer gravação.
    """
    hoje = hoje or date.today()
    lista = cliente.contratos_ativos()
    if not isinstance(lista, list):
        raise ContratosGovErro(f'Resposta inesperada da lista da UG: {str(lista)[:200]}')

    resultado = ResultadoSincronizacao(lidos=len(lista))
    gapbr = om_gapbr()
    contratos_locais = list(Contrato.objects.select_related('empresa'))
    agora = timezone.now()
    itens_por_id = {}

    with transaction.atomic():
        for item in lista:
            if item.get('tipo') != TIPO_ACOMPANHADO or not item.get('id'):
                continue
            campos = _campos_da_lista(item)
            local = localizar_no_siscont(campos['numero'], campos['fornecedor_cnpj'], contratos_locais)
            catalogo = ContratoCatalogo.objects.filter(id_contratosgov=item['id']).first()
            vigente = campos['vigencia_fim'] is None or campos['vigencia_fim'] >= hoje
            if catalogo is None and not (vigente or local):
                continue

            novo = catalogo is None
            if novo:
                catalogo = ContratoCatalogo(id_contratosgov=item['id'])
            for nome, valor in campos.items():
                setattr(catalogo, nome, valor)
            catalogo.na_lista_em = agora
            catalogo.save()
            itens_por_id[catalogo.pk] = item
            resultado.no_catalogo += 1

            if catalogo.situacao == ContratoCatalogo.PENDENTE and local:
                ja_vinculado = ContratoCatalogo.objects.filter(contrato=local).exclude(pk=catalogo.pk).exists()
                if not ja_vinculado:
                    catalogo.situacao = ContratoCatalogo.CLASSIFICADO
                    catalogo.om_beneficiada = gapbr
                    catalogo.contrato = local
                    catalogo.vinculo_automatico = True
                    catalogo.classificado_em = agora
                    catalogo.save()
                    _registrar(catalogo, None, ContratoCatalogo.PENDENTE, None,
                               'Já cadastrado no SISCONT (mesmo número e CNPJ).', automatico=True)
                    resultado.vinculados.append(catalogo)
                    continue
            if novo and catalogo.situacao == ContratoCatalogo.PENDENTE:
                resultado.novos.append(catalogo)

    if sugestoes:
        indice = IndiceOMs.carregar()
        for catalogo in ContratoCatalogo.objects.filter(situacao=ContratoCatalogo.PENDENTE, pk__in=itens_por_id):
            if atualizar_sugestao(catalogo, itens_por_id[catalogo.pk], cliente, indice):
                resultado.sugestoes += 1
            else:
                resultado.sugestoes_falhas += 1

    resultado.pendentes = ContratoCatalogo.objects.filter(situacao=ContratoCatalogo.PENDENTE).count()
    return resultado


# ---------------------------------------------------------------------------- aviso
def emails_administradores():
    User = get_user_model()
    usuarios = User.objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(groups__name='Administradores')).exclude(email='').distinct()
    return sorted({u.email for u in usuarios})


def avisar_novos(novos):
    """Enfileira o e-mail aos Administradores quando surgem contratos novos a classificar."""
    from django.urls import reverse
    from contratos.services.email import enfileirar

    if not novos:
        return None
    linhas = [f'- {c.numero} | {c.fornecedor_nome} | vigência até {c.vigencia_fim:%d/%m/%Y}' if c.vigencia_fim
              else f'- {c.numero} | {c.fornecedor_nome}' for c in novos]
    texto = (
        f'{len(novos)} contrato(s) novo(s) da UG no Contratos.gov.br aguardam a classificação da OM beneficiada:\n\n'
        + '\n'.join(linhas)
        + f'\n\nClassifique em: SISCONT > Contratos a classificar ({reverse("catalogo_contratosgov")}).'
    )
    return enfileirar(emails_administradores(), f'SISCONT: {len(novos)} contrato(s) a classificar',
                      texto, categoria='CONTRATOSGOV')
