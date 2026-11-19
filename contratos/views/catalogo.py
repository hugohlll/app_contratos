"""Catálogo de contratos da UG no Contratos.gov.br e classificação da OM beneficiada (#51).

Acesso só para Administradores.
"""
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from contratos.forms import OrganizacaoMilitarForm
from contratos.models import ContratoCatalogo, OrganizacaoMilitar
from contratos.services.om_beneficiada import ClassificacaoErro, classificar
from contratos.utils import admin_required

from .portal import generico_form, generico_listar

ABAS = [
    (ContratoCatalogo.PENDENTE, 'A classificar'),
    (ContratoCatalogo.CLASSIFICADO, 'Classificados'),
    (ContratoCatalogo.DESCONSIDERADO, 'Desconsiderados'),
]


@admin_required
def catalogo_contratosgov(request):
    aba = request.GET.get('aba', ContratoCatalogo.PENDENTE)
    if aba not in dict(ABAS):
        aba = ContratoCatalogo.PENDENTE
    contagem = dict(ContratoCatalogo.objects.values_list('situacao').annotate(n=Count('id')))
    itens = (ContratoCatalogo.objects.filter(situacao=aba)
             .select_related('om_beneficiada', 'sugestao_om', 'contrato')
             .order_by('vigencia_fim' if aba == ContratoCatalogo.PENDENTE else '-classificado_em'))
    om = request.GET.get('om')
    if aba == ContratoCatalogo.CLASSIFICADO and om:
        itens = itens.filter(om_beneficiada__sigla=om)
    return render(request, 'contratos/catalogo/lista.html', {
        'itens': itens,
        'aba': aba,
        'abas': [(chave, nome, contagem.get(chave, 0)) for chave, nome in ABAS],
        'oms': OrganizacaoMilitar.objects.filter(ativa=True),
        'om_filtro': om or '',
    })


@admin_required
def classificar_catalogo(request, pk):
    catalogo = get_object_or_404(ContratoCatalogo.objects.select_related('om_beneficiada', 'sugestao_om', 'contrato'), pk=pk)
    oms = OrganizacaoMilitar.objects.filter(ativa=True)
    if request.method == 'POST':
        escolha = request.POST.get('om', '')
        desconsiderar = escolha == 'DESCONSIDERAR'
        om = None if desconsiderar else oms.filter(pk=escolha).first() if escolha.isdigit() else None
        try:
            avisos = classificar(catalogo, request.user, om=om, desconsiderar=desconsiderar,
                                 justificativa=request.POST.get('justificativa', ''))
        except ClassificacaoErro as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f'Contrato {catalogo.numero}: {catalogo.get_situacao_display().lower()}'
                             + (f' ({catalogo.om_beneficiada})' if catalogo.om_beneficiada else '') + '.')
            for aviso in avisos:
                messages.warning(request, aviso)
            return redirect('catalogo_contratosgov')
    selecionada = catalogo.om_beneficiada_id or catalogo.sugestao_om_id
    return render(request, 'contratos/catalogo/classificar.html', {
        'c': catalogo,
        'oms': oms,
        'selecionada': selecionada,
        'correcao': catalogo.situacao != ContratoCatalogo.PENDENTE,
        'registros': catalogo.registros.select_related('usuario'),
    })


@admin_required
@require_POST
def classificar_catalogo_lote(request):
    ids = [i for i in request.POST.getlist('selecionados') if i.isdigit()]
    om = OrganizacaoMilitar.objects.filter(pk=request.POST.get('om') or 0, ativa=True).first()
    if not ids or om is None:
        messages.error(request, 'Selecione os contratos e a OM beneficiada.')
        return redirect('catalogo_contratosgov')
    feitos, erros = 0, []
    for catalogo in ContratoCatalogo.objects.filter(pk__in=ids, situacao=ContratoCatalogo.PENDENTE):
        try:
            classificar(catalogo, request.user, om=om)
            feitos += 1
        except ClassificacaoErro as e:
            erros.append(f'{catalogo.numero}: {e}')
    if feitos:
        messages.success(request, f'{feitos} contrato(s) classificado(s) como {om}.')
    for erro in erros:
        messages.error(request, erro)
    return redirect('catalogo_contratosgov')


# ---------------------------------------------------------------------------- cadastro de OMs
@admin_required
def listar_oms(request):
    return generico_listar(
        request, OrganizacaoMilitar, 'contratos/portal/lista_generica.html', 'Organizações Militares',
        'nova_om', 'editar_om',
        [('sigla', 'Sigla'), ('nome', 'Nome'), ('codigo_uasg', 'UASG'), ('prefixos_pi', 'Prefixos de PI')],
    )


@admin_required
def nova_om(request):
    return generico_form(request, OrganizacaoMilitarForm, 'contratos/portal/form_generico.html',
                         'Nova Organização Militar', 'listar_oms')


@admin_required
def editar_om(request, pk):
    instance = get_object_or_404(OrganizacaoMilitar, pk=pk)
    return generico_form(request, OrganizacaoMilitarForm, 'contratos/portal/form_generico.html',
                         f'Editar {instance}', 'listar_oms', instance)
