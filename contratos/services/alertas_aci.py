"""
Alertas internos para a ACI sobre ocorrências do Livro do Fiscal.

Cada evento relevante (criação, exclusão ou mudança de campo-chave) gera uma NotificacaoACI
para cada usuário ativo dos grupos 'Auditores' e 'Administradores' (que acumulam a função de
auditor). Edições apenas de texto não geram alerta, e
o reenvio de uma ocorrência sem alterações (salvamento do Livro) também não.

Os signals em `contratos/signals.py` apenas chamam este serviço; falhas aqui nunca podem
impedir o fiscal de registrar a ocorrência.
"""
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

GRUPOS_ACI = ('Auditores', 'Administradores')
JANELA_AGRUPAMENTO = timedelta(minutes=5)
TAMANHO_RESUMO = 120

# Campos cuja mudança é acompanhada pela ACI (nome do campo -> rótulo legível).
CAMPOS_MONITORADOS = {
    'status_ocorrencia': 'Situação',
    'notificacao_emitida': 'Notificação formal',
    'ciencia_preposto': 'Ciência do preposto',
    'tramite_arc': 'Encaminhamento à ARC/PAAI',
}


def eh_destinatario_aci(user):
    """Recebem e visualizam os alertas os membros de 'Auditores' e 'Administradores'.

    Superusuários sem um desses grupos ficam de fora.
    """
    return bool(
        user and user.is_authenticated and user.groups.filter(name__in=GRUPOS_ACI).exists()
    )


def destinatarios_aci():
    User = get_user_model()
    return User.objects.filter(groups__name__in=GRUPOS_ACI, is_active=True).distinct()


def estado_monitorado(oc):
    return {campo: getattr(oc, campo) for campo in CAMPOS_MONITORADOS}


def _rotulo_valor(oc, campo, valor):
    if isinstance(valor, bool):
        return 'Sim' if valor else 'Não'
    choices = dict(oc._meta.get_field(campo).choices or [])
    return str(choices.get(valor, valor))


def _resumo(texto):
    texto = ' '.join((texto or '').split())
    if len(texto) <= TAMANHO_RESUMO:
        return texto
    return texto[:TAMANHO_RESUMO].rstrip() + '…'


def _responsaveis(controle):
    """Fiscal do Livro, se houver, e integrantes da comissão de fiscalização ativa."""
    from contratos.models import Comissao

    nomes = []
    if controle.agente_id:
        nomes.append(str(controle.agente))
    comissao = Comissao.objects.filter(
        contrato_id=controle.contrato_id, ativa=True, tipo='FISCALIZACAO'
    ).first()
    if comissao:
        integrantes = comissao.integrantes.filter(data_desligamento__isnull=True).select_related(
            'agente__posto', 'funcao'
        ).order_by('ordem', 'id')
        for integ in integrantes:
            nome = str(integ.agente)
            if nome not in nomes:
                nomes.append(nome)
    return nomes


def retrato(oc):
    """Dados da ocorrência copiados para o alerta (sobrevivem à exclusão)."""
    controle = oc.controle
    contrato = controle.contrato
    return {
        'ocorrencia_id': oc.pk,
        'controle_id': controle.pk,
        'contrato_id': contrato.pk,
        'contrato_numero': contrato.numero,
        'empresa': str(contrato.empresa.razao_social) if contrato.empresa_id else '',
        'livro_mes': f"{controle.mes_referencia:02d}/{controle.ano_referencia}",
        'livro_status': controle.get_status_display(),
        'tipo': oc.get_tipo_display(),
        'data_hora': timezone.localtime(oc.data_hora).strftime('%d/%m/%Y %H:%M') if oc.data_hora else '',
        'descricao_resumo': _resumo(oc.descricao),
        'status_ocorrencia': oc.get_status_ocorrencia_display(),
        'responsaveis': _responsaveis(controle),
        'mudancas': [],
    }


def _titulo_atualizacao(mudancas):
    if len(mudancas) != 1:
        return f"Ocorrência atualizada ({len(mudancas)} alterações)"
    m = mudancas[0]
    if m['campo'] == 'status_ocorrencia':
        return f"Status alterado: {m['antes']} → {m['depois']}"
    if m['campo'] == 'notificacao_emitida':
        return 'Notificação formal emitida' if m['depois'] == 'Sim' else 'Notificação formal desmarcada'
    if m['campo'] == 'tramite_arc':
        return 'Encaminhada à ARC/PAAI' if m['depois'] == 'Sim' else 'Encaminhamento à ARC/PAAI desfeito'
    if m['campo'] == 'ciencia_preposto':
        return f"Ciência do preposto: {m['depois']}"
    return 'Ocorrência atualizada'


def _criar_para_todos(evento, titulo, dados, ocorrencia=None, contrato_id=None):
    from contratos.models import NotificacaoACI

    agora = timezone.now()
    NotificacaoACI.objects.bulk_create([
        NotificacaoACI(
            destinatario=user, evento=evento, titulo=titulo, dados=dados,
            ocorrencia=ocorrencia, contrato_id=contrato_id,
            criado_em=agora, atualizado_em=agora,
        )
        for user in destinatarios_aci()
    ])


def _mesclar_mudancas(existentes, novas):
    """Mantém o 'antes' original de cada campo e o 'depois' mais recente; descarta reversões."""
    por_campo = {m['campo']: dict(m) for m in existentes}
    for m in novas:
        if m['campo'] in por_campo:
            por_campo[m['campo']]['depois'] = m['depois']
        else:
            por_campo[m['campo']] = dict(m)
    return [m for m in por_campo.values() if m['antes'] != m['depois']]


def registrar_criacao(oc):
    try:
        dados = retrato(oc)
        _criar_para_todos('OCORRENCIA_CRIADA', 'Nova ocorrência registrada', dados,
                          ocorrencia=oc, contrato_id=dados['contrato_id'])
    except Exception:
        logger.exception("Falha ao gerar alerta da ACI (criação da ocorrência %s)", oc.pk)


def registrar_atualizacao(oc, estado_anterior):
    try:
        mudancas = [
            {
                'campo': campo,
                'rotulo': rotulo,
                'antes': _rotulo_valor(oc, campo, estado_anterior.get(campo)),
                'depois': _rotulo_valor(oc, campo, getattr(oc, campo)),
            }
            for campo, rotulo in CAMPOS_MONITORADOS.items()
            if estado_anterior.get(campo) != getattr(oc, campo)
        ]
        if not mudancas:
            return
        _registrar_mudancas(oc, mudancas)
    except Exception:
        logger.exception("Falha ao gerar alerta da ACI (atualização da ocorrência %s)", oc.pk)


def _registrar_mudancas(oc, mudancas):
    from contratos.models import NotificacaoACI

    agora = timezone.now()
    dados_base = retrato(oc)
    pendentes = {
        n.destinatario_id: n
        for n in NotificacaoACI.objects.filter(
            ocorrencia=oc, evento='OCORRENCIA_ATUALIZADA', lida_em__isnull=True,
            atualizado_em__gte=agora - JANELA_AGRUPAMENTO,
        ).order_by('destinatario_id', '-atualizado_em')
    }

    novos = []
    for user in destinatarios_aci():
        existente = pendentes.get(user.pk)
        if existente:
            mescladas = _mesclar_mudancas(existente.dados.get('mudancas', []), mudancas)
            if not mescladas:
                existente.delete()  # tudo voltou ao estado original: nada a acompanhar
                continue
            existente.dados = {**dados_base, 'mudancas': mescladas}
            existente.titulo = _titulo_atualizacao(mescladas)
            existente.atualizado_em = agora
            existente.save(update_fields=['dados', 'titulo', 'atualizado_em'])
        else:
            novos.append(NotificacaoACI(
                destinatario=user, evento='OCORRENCIA_ATUALIZADA',
                titulo=_titulo_atualizacao(mudancas),
                dados={**dados_base, 'mudancas': mudancas},
                ocorrencia=oc, contrato_id=dados_base['contrato_id'],
                criado_em=agora, atualizado_em=agora,
            ))
    if novos:
        NotificacaoACI.objects.bulk_create(novos)


def preparar_exclusao(oc):
    """Chamado no pre_delete: o retrato precisa ser tirado enquanto os dados existem."""
    try:
        return retrato(oc)
    except Exception:
        logger.exception("Falha ao preparar alerta da ACI (exclusão da ocorrência %s)", oc.pk)
        return None


def registrar_exclusao(dados):
    if not dados:
        return
    try:
        _criar_para_todos('OCORRENCIA_EXCLUIDA', 'Ocorrência excluída', dados,
                          ocorrencia=None, contrato_id=dados['contrato_id'])
    except Exception:
        logger.exception("Falha ao gerar alerta da ACI (exclusão da ocorrência %s)", dados.get('ocorrencia_id'))


def url_destino(notificacao):
    """Livro do mês da ocorrência, rolando até ela quando ainda existe."""
    from contratos.models import ControleExecucao

    if notificacao.ocorrencia_id:
        controle_id = notificacao.ocorrencia.controle_id
        return reverse('visualizar_controle_execucao', args=[controle_id]) + f"#oc-{notificacao.ocorrencia_id}"
    controle_id = notificacao.dados.get('controle_id')
    if controle_id and ControleExecucao.objects.filter(pk=controle_id).exists():
        return reverse('visualizar_controle_execucao', args=[controle_id])
    return None


def nao_lidas(user):
    return user.notificacoes_aci.filter(lida_em__isnull=True)


def marcar_lida(notificacao):
    if notificacao.lida_em is None:
        notificacao.lida_em = timezone.now()
        notificacao.save(update_fields=['lida_em'])


def marcar_todas_lidas(user):
    return nao_lidas(user).update(lida_em=timezone.now())


def filtrar(qs, status=None, evento=None, contrato_id=None):
    if status == 'nao_lidas':
        qs = qs.filter(lida_em__isnull=True)
    elif status == 'lidas':
        qs = qs.filter(lida_em__isnull=False)
    if evento:
        qs = qs.filter(evento=evento)
    if contrato_id:
        qs = qs.filter(contrato_id=contrato_id)
    return qs
