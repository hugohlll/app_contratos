"""Central de alertas da ACI (sino do cabeçalho + página de Notificações)."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from contratos.models import Contrato, NotificacaoACI
from contratos.services import alertas_aci

ITENS_DROPDOWN = 8


def somente_aci(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not alertas_aci.eh_destinatario_aci(request.user):
            return HttpResponseForbidden("Acesso restrito à ACI.")
        return view_func(request, *args, **kwargs)
    return _wrapped


@somente_aci
def notificacoes_lista(request):
    status = request.GET.get('status', 'nao_lidas')
    if status not in ('nao_lidas', 'lidas', 'todas'):
        status = 'nao_lidas'
    evento = request.GET.get('evento', '')
    if evento not in dict(NotificacaoACI.EVENTO_CHOICES):
        evento = ''
    contrato_id = request.GET.get('contrato', '')
    contrato_id = int(contrato_id) if contrato_id.isdigit() else None

    base = request.user.notificacoes_aci.all()
    qs = alertas_aci.filtrar(base, status=status, evento=evento, contrato_id=contrato_id)
    pagina = Paginator(qs.select_related('contrato'), 25).get_page(request.GET.get('page'))

    contratos = Contrato.objects.filter(
        pk__in=base.exclude(contrato__isnull=True).values('contrato_id')
    ).order_by('numero')

    filtros_qs = request.GET.copy()
    filtros_qs.pop('page', None)

    return render(request, 'contratos/portal/notificacoes.html', {
        'pagina': pagina,
        'status': status,
        'evento': evento,
        'contrato_id': contrato_id,
        'contratos': contratos,
        'eventos': NotificacaoACI.EVENTO_CHOICES,
        'total_nao_lidas': alertas_aci.nao_lidas(request.user).count(),
        'filtros_qs': filtros_qs.urlencode(),
    })


@somente_aci
def notificacoes_resumo(request):
    """JSON consumido pelo sino (polling ~60s)."""
    itens = request.user.notificacoes_aci.all()[:ITENS_DROPDOWN]
    return JsonResponse({
        'nao_lidas': alertas_aci.nao_lidas(request.user).count(),
        'itens': [
            {
                'id': n.pk,
                'titulo': n.titulo,
                'evento': n.evento,
                'contrato': n.dados.get('contrato_numero', ''),
                'empresa': n.dados.get('empresa', ''),
                'livro_mes': n.dados.get('livro_mes', ''),
                'resumo': n.dados.get('descricao_resumo', ''),
                'quando': n.atualizado_em.isoformat(),
                'lida': n.lida,
                'url': reverse('notificacao_abrir', args=[n.pk]),
            }
            for n in itens
        ],
    })


@somente_aci
def notificacao_abrir(request, pk):
    notificacao = get_object_or_404(NotificacaoACI, pk=pk, destinatario=request.user)
    alertas_aci.marcar_lida(notificacao)
    destino = alertas_aci.url_destino(notificacao)
    if destino:
        return redirect(destino)
    messages.info(request, "O Livro do Fiscal desta ocorrência não existe mais; o alerta foi marcado como lido.")
    return redirect('notificacoes_lista')


@require_POST
@somente_aci
def notificacoes_marcar_todas(request):
    total = alertas_aci.marcar_todas_lidas(request.user)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'marcadas': total})
    messages.success(request, f"{total} notificação(ões) marcada(s) como lida(s).")
    proximo = request.POST.get('next')
    if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect('notificacoes_lista')
