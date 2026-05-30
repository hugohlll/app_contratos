import os
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.http import HttpResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST
import json
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie

from contratos.models import Contrato, PrestacaoContas, Comissao, Integrante, Agente, CalendarioPrestacao, ApontamentoCorrecao, Setor, PrestacaoContasSetor, ApontamentoCorrecaoSetor
from contratos.forms import PrestacaoContasUploadForm, PrestacaoContasSetorUploadForm
from contratos.utils import admin_required, auditor_required, export_csv_or_xlsx, get_filtro_ativos, is_admin, is_auditor

def portal_prestacao_index(request):
    """Landing page do Portal Público de Prestações."""
    return render(request, 'contratos/prestacao/index.html')

def portal_prestacao_fiscais(request):
    """Página de seleção de Contratos para Fiscais."""
    # Obter apenas contratos ativos
    hoje = date.today()
    contratos = Contrato.objects.filter(
        vigencia_inicio__lte=hoje,
        vigencia_fim__gte=hoje
    ).order_by('numero')
    return render(request, 'contratos/prestacao/fiscais.html', {'contratos': contratos})

def portal_prestacao_gestores(request):
    """Página de seleção de Setores para Gestores."""
    setores = Setor.objects.all()
    return render(request, 'contratos/prestacao/gestores.html', {'setores': setores})

def upload_prestacao_setor(request, setor_id):
    """View pública para envio do PDF de prestação de contas por setor."""
    setor = get_object_or_404(Setor, pk=setor_id)
    
    if request.method == 'POST':
        form = PrestacaoContasSetorUploadForm(request.POST, request.FILES, setor=setor)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
        
        if form.is_valid():
            mes = form.cleaned_data['mes_referencia']
            ano = form.cleaned_data['ano_referencia']
            
            existente = PrestacaoContasSetor.objects.filter(
                setor=setor, mes_referencia=mes, ano_referencia=ano
            ).order_by('-data_envio').first()
            
            if existente and existente.status == 'pendente':
                existente.arquivo = form.cleaned_data.get('arquivo')
                existente.agente = form.cleaned_data.get('agente')
                existente.observacao = form.cleaned_data.get('observacao', '')
                existente.status = 'entregue'
                from django.utils import timezone
                existente.data_envio = timezone.now()
                existente.save()
            else:
                prestacao = form.save(commit=False)
                prestacao.setor = setor
                prestacao.status = 'entregue'
                if existente:
                    prestacao.compor_apresentacao = existente.compor_apresentacao
                prestacao.save()
            
            if is_ajax:
                return JsonResponse({'success': True, 'message': 'Prestação de contas recebida com sucesso!'})
            
            return redirect(f"/prestacoes/gestores/{setor.id}/?enviado=1")
        else:
            if is_ajax:
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = [str(e) for e in error_list]
                if form.non_field_errors():
                    errors['__all__'] = [str(e) for e in form.non_field_errors()]
                return JsonResponse({'success': False, 'errors': errors}, status=400)
                
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            return redirect('upload_prestacao_setor', setor_id=setor.id)
    else:
        form = PrestacaoContasSetorUploadForm(setor=setor)
        historico = PrestacaoContasSetor.objects.filter(
            setor=setor
        ).exclude(status='pendente').order_by('-ano_referencia', '-mes_referencia', '-data_envio')
        
        historico_filtrado = []
        vistos = set()
        for p in historico:
            chave = (p.mes_referencia, p.ano_referencia)
            if chave not in vistos:
                historico_filtrado.append(p)
                vistos.add(chave)
                if len(historico_filtrado) >= 6:
                    break
                    
        context = {
            'setor': setor,
            'form': form,
            'historico': historico_filtrado
        }
        return render(request, 'contratos/prestacao/upload_setor.html', context)


def upload_prestacao(request, contrato_id):
    """View pública para envio do PDF de prestação de contas de contratos."""
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    
    if request.method == 'POST':
        form = PrestacaoContasUploadForm(request.POST, request.FILES, contrato=contrato)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
        
        if form.is_valid():
            mes = form.cleaned_data['mes_referencia']
            ano = form.cleaned_data['ano_referencia']
            
            existente = PrestacaoContas.objects.filter(
                contrato=contrato, mes_referencia=mes, ano_referencia=ano
            ).order_by('-data_envio').first()
            
            if existente and existente.status == 'pendente':
                existente.arquivo = form.cleaned_data.get('arquivo')
                existente.agente = form.cleaned_data.get('agente')
                existente.observacao = form.cleaned_data.get('observacao', '')
                existente.status = 'entregue'
                from django.utils import timezone
                existente.data_envio = timezone.now()
                existente.save()
            else:
                prestacao = form.save(commit=False)
                prestacao.contrato = contrato
                prestacao.status = 'entregue'
                if existente:
                    prestacao.compor_apresentacao = existente.compor_apresentacao
                prestacao.save()
            
            if is_ajax:
                return JsonResponse({'success': True, 'message': 'Prestação de contas recebida com sucesso!'})
            
            return redirect(f"/prestacoes/fiscais/{contrato.id}/?enviado=1")
        else:
            if is_ajax:
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = [str(e) for e in error_list]
                if form.non_field_errors():
                    errors['__all__'] = [str(e) for e in form.non_field_errors()]
                return JsonResponse({'success': False, 'errors': errors}, status=400)
                
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            return redirect('upload_prestacao', contrato_id=contrato.id)
    else:
        form = PrestacaoContasUploadForm(contrato=contrato)
        historico = PrestacaoContas.objects.filter(
            contrato=contrato
        ).exclude(status='pendente').order_by('-ano_referencia', '-mes_referencia', '-data_envio')
        
        historico_filtrado = []
        vistos = set()
        for p in historico:
            chave = (p.mes_referencia, p.ano_referencia)
            if chave not in vistos:
                historico_filtrado.append(p)
                vistos.add(chave)
                if len(historico_filtrado) >= 6:
                    break
                    
        context = {
            'contrato': contrato,
            'form': form,
            'historico': historico_filtrado
        }
        return render(request, 'contratos/prestacao/upload_contrato.html', context)


def _get_dashboard_stats(ano, mes):
    """Retorna as estatísticas do dashboard consolidadas para um dado mês/ano."""
    from datetime import date
    hoje = date.today()
    
    contratos_vigentes = Contrato.objects.filter(
        vigencia_inicio__lte=hoje,
        vigencia_fim__gte=hoje
    )
    total_contratos = contratos_vigentes.count()
    
    from django.db.models import Max
    latest_ids = PrestacaoContas.objects.filter(
        mes_referencia=mes,
        ano_referencia=ano,
        contrato__in=contratos_vigentes
    ).values('contrato_id').annotate(max_id=Max('id')).values_list('max_id', flat=True)
    
    prestacoes_filtradas = PrestacaoContas.objects.filter(id__in=latest_ids)
    
    ok = prestacoes_filtradas.filter(status='ok').count()
    entregues = prestacoes_filtradas.filter(status='entregue').count()
    correcao = prestacoes_filtradas.filter(status='correcao').count()
    # Pendentes são os contratos sem nenhuma entrega OU com entrega em status pendente
    pendentes = total_contratos - (ok + entregues + correcao)
    
    prio_ok = prestacoes_filtradas.filter(status='ok', compor_apresentacao=True).count()
    prio_entregues = prestacoes_filtradas.filter(status='entregue', compor_apresentacao=True).count()
    prio_correcao = prestacoes_filtradas.filter(status='correcao', compor_apresentacao=True).count()
    prio_pendentes = prestacoes_filtradas.filter(status='pendente', compor_apresentacao=True).count()
    
    # Lista ordenada de gestores prioritários
    lista_gestores_prio = prestacoes_filtradas.filter(
        compor_apresentacao=True
    ).select_related('agente', 'agente__posto', 'contrato').order_by(
        'agente__posto__senioridade', 'agente__ordem_manual', 'agente__nome_de_guerra'
    )
    
    gestores_prio = []
    for g in lista_gestores_prio:
        gestores_prio.append({
            'gestor': f"{g.agente.posto.sigla} {g.agente.nome_de_guerra}" if g.agente else "Não informado",
            'agente_id': g.agente.id if g.agente else None,
            'posto_id': g.agente.posto.id if g.agente and g.agente.posto else None,
            'contrato': g.contrato.numero,
            'status': g.status
        })
    
    return {
        'total_contratos': total_contratos,
        'ok_no_mes': ok,
        'entregues_no_mes': entregues,
        'correcao_no_mes': correcao,
        'pendentes_no_mes': pendentes,
        'prio_ok': prio_ok,
        'prio_entregues': prio_entregues,
        'prio_correcao': prio_correcao,
        'prio_pendentes': prio_pendentes,
        'gestores_prio': gestores_prio
    }


@login_required
@ensure_csrf_cookie
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

    stats = _get_dashboard_stats(filtro_ano, filtro_mes)
    
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
    contratos_vigentes = Contrato.objects.filter(
        vigencia_inicio__lte=hoje,
        vigencia_fim__gte=hoje
    ).order_by('numero')
    
    todas_prestacoes = PrestacaoContas.objects.filter(
        ano_referencia__gte=ultimos_3_meses[0][0],
        contrato__in=contratos_vigentes
    ).order_by('id')
    
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

    # Busca todas as prestações dos setores dos últimos 3 meses
    setores = Setor.objects.all().order_by('nome')
    todas_prestacoes_setores = PrestacaoContasSetor.objects.filter(
        ano_referencia__gte=ultimos_3_meses[0][0]
    ).order_by('id')
    
    prestacoes_setor_map = {}
    for p in todas_prestacoes_setores:
        if p.setor_id not in prestacoes_setor_map:
            prestacoes_setor_map[p.setor_id] = {}
        prestacoes_setor_map[p.setor_id][(p.ano_referencia, p.mes_referencia)] = p
        
    matriz_setores = []
    for s in setores:
        entregas = []
        for ano, mes in ultimos_3_meses:
            prestacao = prestacoes_setor_map.get(s.id, {}).get((ano, mes))
            entregas.append({
                'ano': ano,
                'mes': mes,
                'prestacao': prestacao,
                'status': prestacao.status if prestacao else 'pendente'
            })
            
        matriz_setores.append({
            'setor': s,
            'entregas': entregas
        })

    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    context = {
        'is_admin': is_admin(request.user),
        'is_auditor': is_auditor(request.user),
        
        'matriz_contratos': matriz_contratos,
        'matriz_setores': matriz_setores,
        'ultimos_3_meses_tuplas': ultimos_3_meses,
        
        'filtro_mes': filtro_mes,
        'filtro_ano': filtro_ano,
        'meses_choices': [(i, meses_nomes[i-1]) for i in range(1, 13)],
        'anos_choices': range(ano_atual - 2, ano_atual + 1),
    }
    
    # Busca calendário do ano selecionado
    calendarios = {c.mes: c for c in CalendarioPrestacao.objects.filter(ano=filtro_ano)}
    calendario_anual = []
    for m in range(1, 13):
        cal = calendarios.get(m)
        calendario_anual.append({
            'mes': m,
            'nome_mes': meses_nomes[m-1],
            'data_entrega': cal.data_entrega.strftime('%Y-%m-%d') if cal and cal.data_entrega else '',
            'data_apresentacao': cal.data_apresentacao.strftime('%Y-%m-%d') if cal and cal.data_apresentacao else ''
        })
    context['calendario_anual'] = calendario_anual
    
    context.update(stats)
    
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

            stats = _get_dashboard_stats(ano, mes)

            return JsonResponse({
                'success': True,
                'status': 'pendente',
                'status_display': 'Pendente',
                'prestacao_id': None,
                'compor_apresentacao': False,
                'is_admin': is_admin(request.user),
                'is_auditor': is_auditor(request.user),
                'stats': stats
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

    from django.db.models import Max

    # Obter IDs das prestações mais recentes por contrato (pode haver múltiplos envios por período)
    latest_ids = PrestacaoContas.objects.filter(
        mes_referencia=filtro_mes,
        ano_referencia=filtro_ano,
        contrato__in=contratos_vigentes
    ).values('contrato_id').annotate(max_id=Max('id')).values_list('max_id', flat=True)

    prestacoes = PrestacaoContas.objects.filter(
        id__in=latest_ids
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

    justificativa = ""
    if request.method == 'POST':
        if request.content_type == 'application/json':
            try:
                body = json.loads(request.body)
                justificativa = body.get('justificativa', '').strip()
            except json.JSONDecodeError:
                pass
        else:
            justificativa = request.POST.get('justificativa', '').strip()
    else:
        justificativa = request.GET.get('justificativa', '').strip()

    if novo_status == 'correcao' and not justificativa:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'A justificativa de correção é obrigatória.'}, status=400)
        messages.error(request, "A justificativa de correção é obrigatória.")
        return redirect('dashboard_prestacao')

    prestacao.status = novo_status
    prestacao.save()

    if novo_status == 'correcao':
        ApontamentoCorrecao.objects.create(
            prestacao=prestacao,
            autor=request.user,
            descricao=justificativa
        )

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

        stats = _get_dashboard_stats(filtro_ano, filtro_mes)

        return JsonResponse({
            'success': True,
            'status': prestacao.status,
            'status_display': prestacao.get_status_display(),
            'prestacao_id': prestacao.id,
            'compor_apresentacao': prestacao.compor_apresentacao,
            'is_admin': is_admin(request.user),
            'is_auditor': is_auditor(request.user),
            'stats': stats
        })

    messages.success(request, f"Status da prestação do contrato {prestacao.contrato.numero} alterado para {prestacao.get_status_display()}.")
    return redirect('dashboard_prestacao')

@login_required
def toggle_apresentacao_prestacao(request):
    """Ativa/Desativa o checkbox para compor apresentação via POST com JSON."""
    import json
    
    # Apenas admin ou auditor devem poder fazer isso
    if not (is_admin(request.user) or is_auditor(request.user)):
        return JsonResponse({'success': False, 'error': 'Não autorizado'}, status=403)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            checked = data.get('checked', False)
            contrato_id = data.get('contrato_id')
            mes = data.get('mes')
            ano = data.get('ano')
            
            if not contrato_id or not mes or not ano:
                return JsonResponse({'success': False, 'error': 'Parâmetros incompletos.'}, status=400)
                
            try:
                mes = int(mes)
                ano = int(ano)
                contrato_id = int(contrato_id)
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Parâmetros inválidos.'}, status=400)
                
            contrato = get_object_or_404(Contrato, pk=contrato_id)
            
            prestacoes = PrestacaoContas.objects.filter(
                contrato=contrato,
                mes_referencia=mes,
                ano_referencia=ano
            )
            
            if prestacoes.exists():
                prestacoes.update(compor_apresentacao=checked)
                prestacao = prestacoes.order_by('-id').first()
            else:
                prestacao = PrestacaoContas.objects.create(
                    contrato=contrato,
                    mes_referencia=mes,
                    ano_referencia=ano,
                    status='pendente',
                    compor_apresentacao=checked
                )
            
            stats = _get_dashboard_stats(ano, mes)
            
            return JsonResponse({
                'success': True, 
                'checked': prestacao.compor_apresentacao,
                'stats': stats,
                'prestacao_id': prestacao.id
            })
        except Http404:
            return JsonResponse({'success': False, 'error': 'Contrato não encontrado.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    return JsonResponse({'success': False, 'error': 'Método inválido'}, status=405)


@auditor_required
def consolidar_apresentacao(request):
    """Consolida todos os slides prioritários em conformidade em um único PDF para download."""
    import io
    from pypdf import PdfWriter, PdfReader

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

    prestacoes = PrestacaoContas.objects.filter(
        mes_referencia=filtro_mes,
        ano_referencia=filtro_ano,
        contrato__in=contratos_vigentes,
        compor_apresentacao=True,
        status='ok'
    ).select_related('agente', 'agente__posto', 'contrato').order_by(
        'agente__posto__senioridade', 'agente__nome_de_guerra'
    )

    if not prestacoes.exists():
        messages.warning(request, "Nenhum slide prioritário em conformidade para consolidar.")
        qs = urlencode({'mes': filtro_mes, 'ano': filtro_ano})
        return redirect(f"{reverse('dashboard_prestacao')}?{qs}")

    writer = PdfWriter()
    erros = []

    for p in prestacoes:
        if not p.arquivo:
            erros.append(f"Contrato {p.contrato.numero}: registro sem arquivo.")
            continue

        caminho = p.arquivo.path
        if not os.path.isfile(caminho):
            erros.append(f"Contrato {p.contrato.numero}: arquivo não encontrado no servidor.")
            continue

        try:
            reader = PdfReader(caminho)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            erros.append(f"Contrato {p.contrato.numero}: erro ao ler PDF ({e}).")

    if erros:
        for erro in erros:
            messages.warning(request, erro)

    if len(writer.pages) == 0:
        messages.error(request, "Nenhuma página válida encontrada para consolidar.")
        qs = urlencode({'mes': filtro_mes, 'ano': filtro_ano})
        return redirect(f"{reverse('dashboard_prestacao')}?{qs}")

    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)

    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    nome_mes = meses_nomes[filtro_mes - 1] if 1 <= filtro_mes <= 12 else str(filtro_mes)
    nome_arquivo = f"Apresentacao_Consolidada_{nome_mes}_{filtro_ano}.pdf"

    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response

@login_required
@require_POST
def reordenar_gestores_prio(request):
    """
    Recebe um array ordenado de IDs de agentes e atualiza 
    seus campos 'ordem_manual' de acordo com a ordem da lista.
    Restrito a auditores/administradores.
    """
    if not is_auditor(request.user):
        return JsonResponse({'status': 'error', 'message': 'Acesso não autorizado.'}, status=403)
        
    try:
        data = json.loads(request.body)
        agente_ids = data.get('agente_ids', [])
        
        # O array agente_ids vem na ordem estabelecida via drag-and-drop
        for index, agente_id in enumerate(agente_ids):
            Agente.objects.filter(id=agente_id).update(ordem_manual=float(index))
            
        return JsonResponse({'status': 'success', 'message': 'Ordem atualizada com sucesso.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def exportar_historico_prestacao_csv(request):
    """
    Exporta o histórico completo de prestações de contas (todos os envios de todos os contratos).
    Restrito a usuários logados.
    """
    prestacoes = PrestacaoContas.objects.exclude(status='pendente').select_related(
        'contrato', 'contrato__empresa', 'agente', 'agente__posto'
    ).order_by('-data_envio')
    
    headers = [
        'Contrato',
        'PAG',
        'Tipo',
        'Objeto',
        'Empresa',
        'CNPJ',
        'Mês de Referência',
        'Ano de Referência',
        'Fiscal Responsável',
        'Data/Hora de Envio',
        'Status (Situação)',
        'Observação'
    ]
    
    data = []
    for p in prestacoes:
        responsavel = f"{p.agente.posto.sigla} {p.agente.nome_de_guerra}" if p.agente else "Não informado"
        data_envio = p.data_envio.strftime("%d/%m/%Y %H:%M")
        
        data.append([
            p.contrato.numero,
            p.contrato.pag or '-',
            p.contrato.get_tipo_display(),
            p.contrato.objeto,
            p.contrato.empresa.nome_exibicao,
            p.contrato.empresa.cnpj,
            f"{p.mes_referencia:02d}",
            str(p.ano_referencia),
            responsavel,
            data_envio,
            p.get_status_display(),
            p.observacao or '-'
        ])
        
    nome_arquivo = "historico_prestacao_contas_completo"
    return export_csv_or_xlsx(request, nome_arquivo, headers, data)

@login_required
@require_POST
def salvar_calendario_prestacao(request):
    """Salva as datas do calendário anual via AJAX."""
    if not is_admin(request.user) and not is_auditor(request.user):
        return JsonResponse({'success': False, 'error': 'Acesso negado.'}, status=403)
        
    try:
        data = json.loads(request.body)
        ano = int(data.get('ano'))
        mes = int(data.get('mes'))
        data_entrega = data.get('data_entrega') or None
        data_apresentacao = data.get('data_apresentacao') or None
        
        cal, _ = CalendarioPrestacao.objects.get_or_create(ano=ano, mes=mes)
        cal.data_entrega = data_entrega
        cal.data_apresentacao = data_apresentacao
        cal.save()
        
        return JsonResponse({'success': True, 'message': 'Calendário salvo com sucesso.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def download_prestacao_setor(request, pk):
    """Download seguro do PDF de prestação do setor."""
    prestacao = get_object_or_404(PrestacaoContasSetor, pk=pk)
    if not prestacao.arquivo: raise Http404("Arquivo não encontrado no registro.")
    caminho = prestacao.arquivo.path
    if not os.path.exists(caminho): raise Http404("Arquivo físico não encontrado no servidor.")
    with open(caminho, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(caminho)}"'
        return response

@admin_required
def excluir_prestacao_setor(request, pk):
    """Excluir entrega de setor (Apenas Admin)."""
    prestacao = get_object_or_404(PrestacaoContasSetor, pk=pk)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
    if request.method == 'POST' or is_ajax:
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)
        prestacao.delete()
        if is_ajax: return JsonResponse({'success': True})
        messages.success(request, "Prestação de Contas excluída com sucesso.")
        return redirect('dashboard_prestacao')
    return render(request, 'contratos/portal/form_generico.html', {
        'titulo': 'Confirmar Exclusão',
        'mensagem': f"Deseja excluir a prestação do setor {prestacao.setor.nome} ref. {prestacao.mes_referencia:02d}/{prestacao.ano_referencia}?"
    })

@login_required
def alterar_status_prestacao_setor(request, pk, novo_status):
    """Altera o status de uma prestação de contas de setor."""
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
    if not is_auditor(request.user):
        if is_ajax: return JsonResponse({'success': False, 'error': 'Acesso não autorizado.'}, status=403)
        messages.error(request, "Acesso não autorizado.")
        return redirect('dashboard_prestacao')
    prestacao = get_object_or_404(PrestacaoContasSetor, pk=pk)
    if novo_status not in ['entregue', 'correcao', 'ok']:
        if is_ajax: return JsonResponse({'success': False, 'error': 'Status inválido.'}, status=400)
        messages.error(request, "Status inválido.")
        return redirect('dashboard_prestacao')
    justificativa = ""
    if request.method == 'POST':
        if request.content_type == 'application/json':
            try: justificativa = json.loads(request.body).get('justificativa', '').strip()
            except json.JSONDecodeError: pass
        else: justificativa = request.POST.get('justificativa', '').strip()
    if novo_status == 'correcao' and not justificativa:
        if is_ajax: return JsonResponse({'success': False, 'error': 'A justificativa é obrigatória.'}, status=400)
        messages.error(request, "A justificativa é obrigatória.")
        return redirect('dashboard_prestacao')
    prestacao.status = novo_status
    prestacao.save()
    if novo_status == 'correcao':
        ApontamentoCorrecaoSetor.objects.create(
            prestacao=prestacao, autor=request.user, descricao=justificativa
        )
    if is_ajax:
        return JsonResponse({'success': True, 'status': novo_status, 'status_display': prestacao.get_status_display()})
    messages.success(request, f"Status atualizado para {prestacao.get_status_display()}.")
    return redirect('dashboard_prestacao')
