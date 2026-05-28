import os
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.http import HttpResponse, Http404, JsonResponse
from django.conf import settings

from contratos.models import Contrato, PrestacaoContas, Comissao, Integrante, Agente
from contratos.forms import PrestacaoContasUploadForm
from contratos.utils import admin_required, auditor_required, export_csv_or_xlsx, get_filtro_ativos, is_admin, is_auditor

def upload_prestacao(request, contrato_id):
    """View pública para envio do PDF de prestação de contas."""
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    
    if request.method == 'POST':
        form = PrestacaoContasUploadForm(request.POST, request.FILES, contrato=contrato)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
        
        if form.is_valid():
            mes = form.cleaned_data['mes_referencia']
            ano = form.cleaned_data['ano_referencia']
            
            # Se já existir uma entrega, nós a excluímos para substituir
            # (ou podemos atualizar a existente. Optamos por apagar o arquivo velho e substituir)
            existente = PrestacaoContas.objects.filter(
                contrato=contrato, mes_referencia=mes, ano_referencia=ano
            ).first()
            
            if existente:
                if existente.arquivo:
                    # Remove o arquivo físico velho
                    caminho = existente.arquivo.path
                    if os.path.isfile(caminho):
                        os.remove(caminho)
                existente.delete()
            
            # Cria a nova
            prestacao = form.save(commit=False)
            prestacao.contrato = contrato
            prestacao.save()
            
            if is_ajax:
                return JsonResponse({'success': True, 'message': 'Prestação de contas recebida com sucesso!'})
            
            # Redireciona com query param de sucesso
            return redirect(f"/contrato/{contrato.id}/?enviado=1")
        else:
            if is_ajax:
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = [str(e) for e in error_list]
                if form.non_field_errors():
                    errors['__all__'] = [str(e) for e in form.non_field_errors()]
                return JsonResponse({'success': False, 'errors': errors}, status=400)
                
            # Form inválido: Adiciona mensagens de erro e redireciona de volta
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            return redirect('detalhe_contrato', contrato_id=contrato.id)
    else:
        # Se for GET na URL de upload, redireciona para o detalhe
        return redirect('detalhe_contrato', contrato_id=contrato.id)


@login_required
def dashboard_prestacao(request):
    hoje = date.today()
    mes_atual = hoje.month
    ano_atual = hoje.year

    # Obtém meses e anos dos filtros de forma robusta
    try:
        filtro_mes = int(request.GET.get('mes', mes_atual))
    except (ValueError, TypeError):
        filtro_mes = mes_atual

    try:
        raw_ano = request.GET.get('ano', str(ano_atual)).replace('.', '')
        filtro_ano = int(raw_ano)
    except (ValueError, TypeError):
        filtro_ano = ano_atual

    contratos_vigentes = Contrato.objects.filter(
        vigencia_inicio__lte=hoje,
        vigencia_fim__gte=hoje
    ).order_by('numero')
    
    total_contratos = contratos_vigentes.count()
    
    # Prestações no mês/ano filtrado para contratos vigentes
    prestacoes_filtradas = PrestacaoContas.objects.filter(
        mes_referencia=filtro_mes,
        ano_referencia=filtro_ano,
        contrato__in=contratos_vigentes
    )
    
    ok_no_mes = prestacoes_filtradas.filter(status='ok').count()
    entregues_no_mes = prestacoes_filtradas.filter(status='entregue').count()
    correcao_no_mes = prestacoes_filtradas.filter(status='correcao').count()
    pendentes_no_mes = total_contratos - prestacoes_filtradas.count()
    
    # Construir tabela-matriz (Últimos 3 meses)
    # Lista de tuplas (ano, mes) dos últimos 3 meses
    ultimos_3_meses = []
    _ano = hoje.year
    _mes = hoje.month
    for _ in range(3):
        ultimos_3_meses.append((_ano, _mes))
        _mes -= 1
        if _mes == 0:
            _mes = 12
            _ano -= 1
    ultimos_3_meses.reverse() # Colocar em ordem cronológica
    
    # Mapear as entregas por contrato para acesso rápido na view
    # estrutura: {contrato_id: {(ano, mes): prestacao_id}}
    prestacoes_map = {}
    
    # Busca todas as prestações dos últimos 3 meses
    todas_prestacoes = PrestacaoContas.objects.filter(
        ano_referencia__gte=ultimos_3_meses[0][0],
        contrato__in=contratos_vigentes
    )
    
    for p in todas_prestacoes:
        if p.contrato_id not in prestacoes_map:
            prestacoes_map[p.contrato_id] = {}
        prestacoes_map[p.contrato_id][(p.ano_referencia, p.mes_referencia)] = p

    # Monta matriz estruturada para o template
    matriz_contratos = []
    for c in contratos_vigentes:
        entregas = []
        for ano, mes in ultimos_3_meses:
            prestacao = prestacoes_map.get(c.id, {}).get((ano, mes))
            entregas.append({
                'ano': ano,
                'mes': mes,
                'prestacao': prestacao, # Pode ser None
                'status': prestacao.status if prestacao else 'pendente'
            })
            
        matriz_contratos.append({
            'contrato': c,
            'entregas': entregas
        })

    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    context = {
        'total_contratos': total_contratos,
        'ok_no_mes': ok_no_mes,
        'entregues_no_mes': entregues_no_mes,
        'correcao_no_mes': correcao_no_mes,
        'pendentes_no_mes': pendentes_no_mes,
        'is_admin': is_admin(request.user),
        'is_auditor': is_auditor(request.user),
        
        'matriz_contratos': matriz_contratos,
        'ultimos_3_meses_tuplas': ultimos_3_meses,
        
        'filtro_mes': filtro_mes,
        'filtro_ano': filtro_ano,
        'meses_choices': [(i, meses_nomes[i-1]) for i in range(1, 13)],
        'anos_choices': range(ano_atual - 2, ano_atual + 1),
    }
    
    return render(request, 'contratos/dashboard_prestacao.html', context)


@login_required
def download_prestacao(request, pk):
    """Download seguro do PDF."""
    prestacao = get_object_or_404(PrestacaoContas, pk=pk)
    
    if not prestacao.arquivo:
        raise Http404("Arquivo não encontrado no registro.")
        
    caminho = prestacao.arquivo.path
    if not os.path.exists(caminho):
        raise Http404("Arquivo físico não encontrado no servidor.")
        
    with open(caminho, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(caminho)}"'
        return response


@admin_required
def excluir_prestacao(request, pk):
    """Excluir entrega (Apenas Admin)."""
    prestacao = get_object_or_404(PrestacaoContas, pk=pk)
    
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
    
    if request.method == 'POST' or is_ajax:
        # Apagar o arquivo físico
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)
            
        prestacao.delete()
        
        if is_ajax:
            # Recalcular estatísticas para o gráfico
            hoje = date.today()
            mes = request.GET.get('mes')
            ano = request.GET.get('ano')
            
            if mes and ano:
                try:
                    mes = int(mes)
                    ano = int(ano)
                except ValueError:
                    mes = ano = None
            
            # Se não vieram filtros válidos na requisição AJAX, pegamos do mês atual
            if not mes or not ano:
                mes = hoje.month
                ano = hoje.year

            total_contratos = Contrato.objects.filter(
                vigencia_inicio__lte=hoje,
                vigencia_fim__gte=hoje
            ).count()
            
            entregues_no_mes = PrestacaoContas.objects.filter(mes_referencia=mes, ano_referencia=ano, status='entregue').count()
            correcao_no_mes = PrestacaoContas.objects.filter(mes_referencia=mes, ano_referencia=ano, status='correcao').count()
            ok_no_mes = PrestacaoContas.objects.filter(mes_referencia=mes, ano_referencia=ano, status='ok').count()
            pendentes_no_mes = total_contratos - (entregues_no_mes + correcao_no_mes + ok_no_mes)

            return JsonResponse({
                'success': True,
                'status': 'pendente',
                'status_display': 'Pendente',
                'prestacao_id': None,
                'compor_apresentacao': False,
                'is_admin': is_admin(request.user),
                'is_auditor': is_auditor(request.user),
                'stats': {
                    'ok_no_mes': ok_no_mes,
                    'entregues_no_mes': entregues_no_mes,
                    'correcao_no_mes': correcao_no_mes,
                    'pendentes_no_mes': pendentes_no_mes,
                    'total_contratos': total_contratos
                }
            })
            
        messages.success(request, "Prestação de Contas excluída com sucesso.")
        return redirect('dashboard_prestacao')
        
    return render(request, 'contratos/portal/form_generico.html', {
        'titulo': 'Confirmar Exclusão',
        'mensagem': f"Deseja excluir a prestação do contrato {prestacao.contrato.numero} ref. {prestacao.mes_referencia:02d}/{prestacao.ano_referencia}?"
    })


@login_required
def exportar_prestacao_csv(request):
    """Exporta as prestações de contas (entregues e pendentes) do mês e ano selecionados."""
    hoje = date.today()
    mes_atual = hoje.month
    ano_atual = hoje.year

    try:
        filtro_mes = int(request.GET.get('mes', mes_atual))
    except (ValueError, TypeError):
        filtro_mes = mes_atual

    try:
        raw_ano = request.GET.get('ano', str(ano_atual)).replace('.', '')
        filtro_ano = int(raw_ano)
    except (ValueError, TypeError):
        filtro_ano = ano_atual

    contratos_vigentes = Contrato.objects.filter(
        vigencia_inicio__lte=hoje,
        vigencia_fim__gte=hoje
    ).order_by('numero').select_related('empresa')

    # Prestações no mês/ano filtrado para contratos vigentes
    prestacoes = PrestacaoContas.objects.filter(
        mes_referencia=filtro_mes,
        ano_referencia=filtro_ano,
        contrato__in=contratos_vigentes
    ).select_related('contrato', 'agente__posto')

    prestacoes_map = {p.contrato_id: p for p in prestacoes}

    headers = [
        'Contrato',
        'PAG',
        'Tipo',
        'Objeto',
        'Início da Vigência',
        'Fim da Vigência',
        'Valor Total',
        'Empresa',
        'CNPJ',
        'Situação',
        'Responsável pela Entrega',
        'Data/Hora do Último Envio'
    ]
    data = []

    for c in contratos_vigentes:
        p = prestacoes_map.get(c.id)
        if p:
            situacao = p.get_status_display()
            responsavel = f"{p.agente.posto.sigla} {p.agente.nome_de_guerra}" if p.agente else "Não informado"
            data_envio = p.data_envio.strftime("%d/%m/%Y %H:%M")
        else:
            situacao = 'Pendente'
            responsavel = '-'
            data_envio = '-'

        data.append([
            c.numero,
            c.pag or '-',
            c.get_tipo_display(),
            c.objeto,
            c.vigencia_inicio.strftime("%d/%m/%Y"),
            c.vigencia_fim.strftime("%d/%m/%Y"),
            float(c.valor_total),
            c.empresa.razao_social,
            c.empresa.cnpj,
            situacao,
            responsavel,
            data_envio
        ])

    nome_arquivo = f"prestacao_contas_{filtro_mes:02d}_{filtro_ano}"
    return export_csv_or_xlsx(request, nome_arquivo, headers, data)


@login_required
def alterar_status_prestacao(request, pk, novo_status):
    """Altera o status de uma prestação de contas (Administradores/Auditores)."""
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'

    if not is_auditor(request.user):
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Acesso não autorizado.'}, status=403)
        messages.error(request, "Acesso não autorizado.")
        return redirect('dashboard_prestacao')

    prestacao = get_object_or_404(PrestacaoContas, pk=pk)
    if novo_status not in ['entregue', 'correcao', 'ok']:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Status inválido.'}, status=400)
        messages.error(request, "Status inválido.")
        return redirect('dashboard_prestacao')

    prestacao.status = novo_status
    prestacao.save()

    if is_ajax:
        # Se for AJAX, não inserimos a mensagem de sucesso para não poluir futuras páginas
        # e calculamos as estatísticas atualizadas do mês para o gráfico
        hoje = date.today()
        try:
            filtro_mes = int(request.GET.get('mes', hoje.month))
        except (ValueError, TypeError):
            filtro_mes = hoje.month

        try:
            raw_ano = request.GET.get('ano', str(hoje.year)).replace('.', '')
            filtro_ano = int(raw_ano)
        except (ValueError, TypeError):
            filtro_ano = hoje.year

        contratos_vigentes = Contrato.objects.filter(
            vigencia_inicio__lte=hoje,
            vigencia_fim__gte=hoje
        )
        total_contratos = contratos_vigentes.count()
        prestacoes_filtradas = PrestacaoContas.objects.filter(
            mes_referencia=filtro_mes,
            ano_referencia=filtro_ano,
            contrato__in=contratos_vigentes
        )
        
        ok_no_mes = prestacoes_filtradas.filter(status='ok').count()
        entregues_no_mes = prestacoes_filtradas.filter(status='entregue').count()
        correcao_no_mes = prestacoes_filtradas.filter(status='correcao').count()
        pendentes_no_mes = total_contratos - prestacoes_filtradas.count()

        return JsonResponse({
            'success': True,
            'status': prestacao.status,
            'status_display': prestacao.get_status_display(),
            'prestacao_id': prestacao.id,
            'compor_apresentacao': prestacao.compor_apresentacao,
            'is_admin': is_admin(request.user),
            'is_auditor': is_auditor(request.user),
            'stats': {
                'ok_no_mes': ok_no_mes,
                'entregues_no_mes': entregues_no_mes,
                'correcao_no_mes': correcao_no_mes,
                'pendentes_no_mes': pendentes_no_mes,
                'total_contratos': total_contratos
            }
        })

    messages.success(request, f"Status da prestação do contrato {prestacao.contrato.numero} alterado para {prestacao.get_status_display()}.")
    return redirect('dashboard_prestacao')

@login_required
def toggle_apresentacao_prestacao(request, pk):
    """Ativa/Desativa o checkbox para compor apresentação."""
    import json
    
    prestacao = get_object_or_404(PrestacaoContas, pk=pk)
    
    # Apenas admin ou auditor devem poder fazer isso
    if not (is_admin(request.user) or is_auditor(request.user)):
        return JsonResponse({'success': False, 'error': 'Não autorizado'}, status=403)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            checked = data.get('checked', False)
                
            prestacao.compor_apresentacao = checked
            prestacao.save(update_fields=['compor_apresentacao'])
            return JsonResponse({'success': True, 'checked': prestacao.compor_apresentacao})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    return JsonResponse({'success': False, 'error': 'Método inválido'}, status=405)
