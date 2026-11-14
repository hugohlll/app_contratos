"""
Indicadores do Painel de Auditoria.

Cada indicador devolve as linhas detalhadas já classificadas por segmento
(a fatia ou barra do gráfico). O painel usa as mesmas linhas para calcular
as contagens dos gráficos, e o endpoint de detalhe as usa para listar os
registros de um segmento. Assim, o número exibido no gráfico é sempre igual
à quantidade de linhas mostradas no detalhe.
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

from django.db.models import Count, Q

from contratos.models import (
    Agente, Comissao, Contrato, Integrante, DIAS_VALIDADE_QUALIFICACAO,
)
from contratos.utils import get_filtro_ativos

SEGMENTO_TODOS = 'todos'


@dataclass
class Linha:
    """Uma linha do detalhe. `segmento` indica a fatia/barra a que pertence."""
    segmento: str
    celulas: list
    contrato_id: Optional[int] = None
    rotulo_segmento: str = ''


@dataclass
class Indicador:
    chave: str
    titulo: str
    colunas: list
    carregar: Callable[[date], list]
    # Segmentos fixos (chave -> rótulo). Vazio = segmentos dinâmicos (ex.: id do agente).
    segmentos: dict = field(default_factory=dict)
    nome_arquivo: str = ''
    # Coluna que recebe o link para o contrato (quando a linha tem contrato_id).
    coluna_contrato: int = 0

    def rotulo(self, segmento, linhas):
        if segmento == SEGMENTO_TODOS:
            return 'Todos'
        if segmento in self.segmentos:
            return self.segmentos[segmento]
        for linha in linhas:
            if linha.segmento == segmento and linha.rotulo_segmento:
                return linha.rotulo_segmento
        return segmento

    def segmento_valido(self, segmento):
        if segmento == SEGMENTO_TODOS:
            return True
        if self.segmentos:
            return segmento in self.segmentos
        return segmento.isdigit()


def _fmt(d):
    return d.strftime('%d/%m/%Y') if d else '-'


def _nome_agente(agente, posto=None):
    sigla = posto.sigla if posto else agente.posto.sigla
    return f"{sigla} {agente.nome_de_guerra}"


def _identificacao_comissao(comissao):
    """Número do contrato e empresa; para comissões sem contrato, tipo e descrição."""
    if comissao.contrato:
        return comissao.contrato.numero, comissao.contrato.empresa.nome_exibicao
    return comissao.get_tipo_display(), (comissao.descricao_objeto or '-')[:80]


# ---------------------------------------------------------------------------
# Regras de classificação (mantidas aqui para serem testadas isoladamente)
# ---------------------------------------------------------------------------

def classificar_vencimento_comissao(dias):
    if dias <= 7:
        return 'critico'
    if dias <= 15:
        return 'alerta'
    return 'normal'


def classificar_vencimento_contrato(dias):
    if dias <= 90:
        return 'ate_90'
    if dias <= 120:
        return 'entre_90_120'
    return 'apos_120'


def classificar_qualificacao(data_ultimo_curso, hoje):
    if not data_ultimo_curso:
        return 'sem_curso'
    if data_ultimo_curso < hoje - timedelta(days=DIAS_VALIDADE_QUALIFICACAO):
        return 'vencidos'
    return 'em_dia'


def classificar_permanencia(dias):
    """Classe Bootstrap usada no radar: > 2 anos perigo, > 1 ano alerta."""
    if dias > 730:
        return 'bg-danger'
    if dias > 365:
        return 'bg-warning text-dark'
    return 'bg-success'


# ---------------------------------------------------------------------------
# Cálculos
# ---------------------------------------------------------------------------

def vencimentos_comissoes(hoje):
    """Comissões ativas com término (próprio ou da vigência do contrato) ainda não vencido."""
    itens = []
    comissoes = Comissao.objects.filter(ativa=True).select_related('contrato__empresa')
    for comissao in comissoes:
        fim = comissao.data_fim or (comissao.contrato.vigencia_fim if comissao.contrato else None)
        if not fim or fim < hoje:
            continue
        dias = (fim - hoje).days
        itens.append((dias, comissao, fim))
    itens.sort(key=lambda x: x[0])
    return itens


def _linhas_vencimento_comissoes(hoje):
    rotulos = INDICADORES['vencimento-comissoes'].segmentos
    linhas = []
    for dias, comissao, fim in vencimentos_comissoes(hoje):
        segmento = classificar_vencimento_comissao(dias)
        numero, empresa = _identificacao_comissao(comissao)
        linhas.append(Linha(
            segmento=segmento,
            celulas=[numero, empresa, comissao.get_tipo_display(), _fmt(fim), dias,
                     rotulos[segmento].split(' (')[0]],
            contrato_id=comissao.contrato_id,
        ))
    return linhas


def agentes_ativos_qs():
    ids = Integrante.objects.filter(get_filtro_ativos()).values_list('agente', flat=True).distinct()
    return Agente.objects.filter(id__in=ids).select_related('posto')


def _contratos_por_agente():
    """{agente_id: [números de contrato/comissão das designações ativas]}"""
    mapa = defaultdict(list)
    integrantes = Integrante.objects.filter(get_filtro_ativos()).select_related('comissao__contrato')
    for i in integrantes:
        ref = i.comissao.contrato.numero if i.comissao.contrato else i.comissao.get_tipo_display()
        if ref not in mapa[i.agente_id]:
            mapa[i.agente_id].append(ref)
    return mapa


def _linhas_qualificacao(hoje):
    rotulos = INDICADORES['qualificacao'].segmentos
    contratos = _contratos_por_agente()
    linhas = []
    agentes = agentes_ativos_qs().order_by('posto__senioridade', 'nome_de_guerra')
    for ag in agentes:
        segmento = classificar_qualificacao(ag.data_ultimo_curso, hoje)
        linhas.append(Linha(
            segmento=segmento,
            celulas=[_nome_agente(ag), ag.saram,
                     _fmt(ag.data_ultimo_curso) if ag.data_ultimo_curso else 'Não realizado',
                     _fmt(ag.data_validade_curso), ', '.join(contratos.get(ag.id, [])),
                     rotulos[segmento]],
        ))
    return linhas


def radar_permanencia(hoje):
    """
    Tempo contínuo de cada designação ativa, somando designações anteriores
    encadeadas (mesmo contrato, tipo de comissão, agente e função, em que a
    anterior termina no dia imediatamente anterior ao início da seguinte).

    Faz uma única consulta para o histórico, em vez de uma por integrante.
    """
    ativos = list(
        Integrante.objects.filter(get_filtro_ativos())
        .select_related('agente__posto', 'funcao', 'comissao__contrato__empresa')
    )
    agentes_ids = {i.agente_id for i in ativos}

    # Índice: (contrato, tipo, agente, função) -> {data de término: data de início}
    indice = defaultdict(dict)
    historico = (
        Integrante.objects.filter(agente_id__in=agentes_ids, comissao__contrato__isnull=False)
        .values('comissao__contrato_id', 'comissao__tipo', 'agente_id', 'funcao_id',
                'data_inicio', 'data_fim', 'data_desligamento')
        .order_by('ordem', 'id')
    )
    for h in historico:
        chave = (h['comissao__contrato_id'], h['comissao__tipo'], h['agente_id'], h['funcao_id'])
        for termino in (h['data_fim'], h['data_desligamento']):
            if termino:
                # Mantém a primeira ocorrência, como o .first() da versão anterior.
                indice[chave].setdefault(termino, h['data_inicio'])

    radar = []
    for atual in ativos:
        inicio_real = atual.data_inicio
        if atual.comissao.contrato_id:
            chave = (atual.comissao.contrato_id, atual.comissao.tipo, atual.agente_id, atual.funcao_id)
            vistos = set()
            while inicio_real not in vistos:
                vistos.add(inicio_real)
                anterior = indice[chave].get(inicio_real - timedelta(days=1))
                if not anterior:
                    break
                inicio_real = anterior

        dias = (hoje - inicio_real).days
        anos, meses = dias // 365, (dias % 365) // 30
        radar.append({
            'integrante': atual,
            'agente': atual.agente,
            'funcao': atual.funcao,
            'contrato': atual.comissao.contrato,
            'comissao': atual.comissao,
            'dias_totais': dias,
            'tempo_formatado': f"{anos}a {meses}m ({dias} dias)",
            'inicio_real': inicio_real,
            'classe_tempo': classificar_permanencia(dias),
            'inicio_original': atual.data_inicio,
        })

    radar.sort(key=lambda x: (-x['dias_totais'], x['agente'].posto.senioridade, x['agente'].nome_de_guerra))
    return radar


def _linhas_permanencia(hoje):
    linhas = []
    for item in radar_permanencia(hoje):
        numero, empresa = _identificacao_comissao(item['comissao'])
        nome = _nome_agente(item['agente'])
        linhas.append(Linha(
            segmento=str(item['agente'].id),
            rotulo_segmento=nome,
            celulas=[nome, item['funcao'].titulo, numero, empresa,
                     _fmt(item['inicio_real']), item['tempo_formatado']],
            contrato_id=item['contrato'].id if item['contrato'] else None,
        ))
    return linhas


def integrantes_fiscais():
    return Integrante.objects.filter(get_filtro_ativos(), funcao__titulo='Fiscal')


def sobrecarga_fiscais(limite=None):
    """Agentes com designação ativa como Fiscal, anotados com `total_atuacoes`."""
    fiscais = integrantes_fiscais()
    qs = Agente.objects.filter(integrante__in=fiscais).annotate(
        total_atuacoes=Count('integrante', filter=Q(integrante__in=fiscais))
    ).filter(total_atuacoes__gt=0).select_related('posto').order_by(
        '-total_atuacoes', 'posto__senioridade', 'nome_de_guerra'
    )
    return qs[:limite] if limite else qs


def media_limite_fiscais(hoje):
    total_contratos = Contrato.objects.filter(vigencia_fim__gte=hoje).count()
    total_fiscais = integrantes_fiscais().values('agente').distinct().count()
    return math.ceil(total_contratos / total_fiscais) if total_fiscais else 0


def _linhas_sobrecarga(hoje):
    linhas = []
    fiscais = integrantes_fiscais().select_related(
        'agente__posto', 'comissao__contrato__empresa'
    ).order_by('agente__posto__senioridade', 'agente__nome_de_guerra')
    for i in fiscais:
        numero, empresa = _identificacao_comissao(i.comissao)
        nome = _nome_agente(i.agente)
        fim = i.comissao.contrato.vigencia_fim if i.comissao.contrato else i.comissao.data_fim
        linhas.append(Linha(
            segmento=str(i.agente_id),
            rotulo_segmento=nome,
            celulas=[nome, numero, empresa, _fmt(i.data_inicio), _fmt(fim)],
            contrato_id=i.comissao.contrato_id,
        ))
    return linhas


def contratos_vigentes_qs(hoje):
    return Contrato.objects.filter(vigencia_fim__gte=hoje).select_related('empresa').order_by('vigencia_fim')


def _linhas_vencimento_contratos(hoje):
    rotulos = INDICADORES['vencimento-contratos'].segmentos
    linhas = []
    for c in contratos_vigentes_qs(hoje):
        dias = (c.vigencia_fim - hoje).days
        segmento = classificar_vencimento_contrato(dias)
        linhas.append(Linha(
            segmento=segmento,
            celulas=[c.numero, c.empresa.nome_exibicao, _fmt(c.vigencia_fim), dias, rotulos[segmento]],
            contrato_id=c.id,
        ))
    return linhas


def contratos_risco_qs(hoje):
    """Contratos vigentes sem nenhum integrante ativo em comissão de fiscalização ativa."""
    return Contrato.objects.filter(vigencia_fim__gte=hoje).annotate(
        fiscais_ativos=Count(
            'comissoes__integrantes',
            filter=Q(comissoes__tipo='FISCALIZACAO') & Q(comissoes__ativa=True)
            & Q(comissoes__integrantes__in=Integrante.objects.filter(get_filtro_ativos()))
        )
    ).filter(fiscais_ativos=0).select_related('empresa').order_by('vigencia_fim')


def _linhas_contratos_risco(hoje):
    return [
        Linha(segmento='todos', celulas=[c.numero, c.empresa.nome_exibicao, _fmt(c.vigencia_fim),
                                         (c.vigencia_fim - hoje).days], contrato_id=c.id)
        for c in contratos_risco_qs(hoje)
    ]


def _linhas_contratos_vigentes(hoje):
    return [
        Linha(segmento='todos', celulas=[c.numero, c.empresa.nome_exibicao, (c.objeto or '')[:120],
                                         _fmt(c.vigencia_fim), (c.vigencia_fim - hoje).days], contrato_id=c.id)
        for c in contratos_vigentes_qs(hoje)
    ]


def _linhas_militares_designados(hoje):
    contratos = _contratos_por_agente()
    designacoes = dict(
        Integrante.objects.filter(get_filtro_ativos()).values('agente').annotate(n=Count('id')).values_list('agente', 'n')
    )
    return [
        Linha(segmento='todos', celulas=[_nome_agente(ag), ag.saram, designacoes.get(ag.id, 0),
                                         ', '.join(contratos.get(ag.id, []))])
        for ag in agentes_ativos_qs().order_by('posto__senioridade', 'nome_de_guerra')
    ]


INDICADORES = {
    'vencimento-comissoes': Indicador(
        chave='vencimento-comissoes',
        titulo='Vencimento das Comissões',
        colunas=['Contrato', 'Empresa / Objeto', 'Comissão', 'Término', 'Dias restantes', 'Situação'],
        segmentos={'critico': 'Crítico (≤7 dias)', 'alerta': 'Alerta (8-15 dias)', 'normal': 'Normal (>15 dias)'},
        carregar=_linhas_vencimento_comissoes,
        nome_arquivo='detalhe_vencimento_comissoes',
    ),
    'qualificacao': Indicador(
        chave='qualificacao',
        titulo='Qualificação dos Agentes',
        colunas=['Militar', 'SARAM', 'Último curso', 'Validade', 'Contratos', 'Situação'],
        segmentos={'em_dia': 'Em Dia', 'vencidos': 'Vencido', 'sem_curso': 'Sem Curso'},
        carregar=_linhas_qualificacao,
        nome_arquivo='detalhe_qualificacao',
    ),
    'permanencia': Indicador(
        chave='permanencia',
        titulo='Radar de Permanência',
        colunas=['Militar', 'Função', 'Contrato', 'Empresa / Objeto', 'Início real', 'Tempo'],
        carregar=_linhas_permanencia,
        nome_arquivo='detalhe_permanencia',
        coluna_contrato=2,
    ),
    'sobrecarga': Indicador(
        chave='sobrecarga',
        titulo='Sobrecarga de Fiscais',
        colunas=['Fiscal', 'Contrato', 'Empresa / Objeto', 'Início designação', 'Fim vigência'],
        carregar=_linhas_sobrecarga,
        nome_arquivo='detalhe_sobrecarga_fiscais',
        coluna_contrato=1,
    ),
    'vencimento-contratos': Indicador(
        chave='vencimento-contratos',
        titulo='Vencimento dos Contratos',
        colunas=['Contrato', 'Empresa', 'Vencimento', 'Dias restantes', 'Faixa'],
        segmentos={'ate_90': '≤ 90 dias', 'entre_90_120': '90-120 dias', 'apos_120': '> 120 dias'},
        carregar=_linhas_vencimento_contratos,
        nome_arquivo='detalhe_vencimento_contratos',
    ),
    'contratos-vigentes': Indicador(
        chave='contratos-vigentes',
        titulo='Contratos Vigentes',
        colunas=['Contrato', 'Empresa', 'Objeto', 'Vencimento', 'Dias restantes'],
        carregar=_linhas_contratos_vigentes,
        nome_arquivo='detalhe_contratos_vigentes',
    ),
    'militares-designados': Indicador(
        chave='militares-designados',
        titulo='Militares Designados',
        colunas=['Militar', 'SARAM', 'Designações ativas', 'Contratos'],
        carregar=_linhas_militares_designados,
        nome_arquivo='detalhe_militares_designados',
    ),
    'contratos-risco': Indicador(
        chave='contratos-risco',
        titulo='Contratos sem Equipe de Fiscalização',
        colunas=['Contrato', 'Empresa', 'Vencimento', 'Dias restantes'],
        carregar=_linhas_contratos_risco,
        nome_arquivo='detalhe_contratos_risco',
    ),
}


def detalhar(chave, segmento, hoje=None):
    """
    Devolve (indicador, rótulo do segmento, linhas filtradas).
    Levanta KeyError para indicador desconhecido e ValueError para segmento inválido.
    """
    hoje = hoje or date.today()
    indicador = INDICADORES[chave]
    if not indicador.segmento_valido(segmento):
        raise ValueError(segmento)
    linhas = indicador.carregar(hoje)
    filtradas = linhas if segmento == SEGMENTO_TODOS else [l for l in linhas if l.segmento == segmento]
    return indicador, indicador.rotulo(segmento, linhas), filtradas


def contar(chave, hoje=None):
    """{segmento: quantidade} para um indicador de segmentos fixos."""
    hoje = hoje or date.today()
    indicador = INDICADORES[chave]
    contagem = {s: 0 for s in indicador.segmentos}
    for linha in indicador.carregar(hoje):
        contagem[linha.segmento] = contagem.get(linha.segmento, 0) + 1
    return contagem
