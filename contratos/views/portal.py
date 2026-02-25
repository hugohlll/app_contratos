from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from contratos.utils import admin_required, auditor_required
from django.contrib import messages
from django.contrib import messages
from django.urls import reverse
from django.db.models import Prefetch, Case, When, Value, IntegerField
from ..models import Empresa, Contrato, Agente, Integrante, Comissao, Funcao
from ..forms import EmpresaForm, ContratoForm, AgenteForm, IntegranteForm, ComissaoForm


def _get_integrantes_ordenados():
    """Retorna um queryset de Integrante ordenado pela ordem manual."""
    return Integrante.objects.select_related('agente', 'funcao', 'posto_graduacao').order_by('ordem', 'funcao__titulo')

@auditor_required
def portal_home(request):
    """Tela inicial do Portal do Lançador"""
    context = {
        'total_contratos': Contrato.objects.count(),
        'total_agentes': Agente.objects.count(),
        'total_integrantes': Integrante.objects.count(),
        'total_comissoes': Comissao.objects.count(),
    }
    return render(request, 'contratos/portal/home.html', context)

# --- GENERIC CRUD HELPERS ---

def generico_listar(request, model, template_name, titulo, url_novo, url_editar, fields_display, url_exportar=None, arquivo_exportacao=None):
    items = model.objects.all()
    context = {
        'items': items,
        'titulo': titulo,
        'url_novo': url_novo,
        'url_editar': url_editar,
        'url_exportar': url_exportar,
        'arquivo_exportacao': arquivo_exportacao,
        'fields': fields_display # Lista de tuplas (atributo, label)
    }
    return render(request, template_name, context)

def generico_form(request, form_class, template_name, titulo, url_sucesso, instance=None):
    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f'{titulo} salvo com sucesso!')
            return redirect(url_sucesso)
    else:
        form = form_class(instance=instance)
    
    return render(request, template_name, {
        'form': form,
        'titulo': titulo
    })

import csv
import io
from django.http import HttpResponse

# --- EMPRESAS ---
@auditor_required
def listar_empresas(request):
    return generico_listar(
        request, Empresa, 'contratos/portal/lista_generica.html', 'Empresas', 
        'nova_empresa', 'editar_empresa', 
        [('razao_social', 'Razão Social'), ('cnpj', 'CNPJ')],
        url_exportar='exportar_empresas_csv',
        arquivo_exportacao='empresas.csv'
    )

@auditor_required
def exportar_empresas_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="empresas.csv"'
    response.write('\ufeff')  # BOM
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Razão Social', 'CNPJ'])
    
    for empresa in Empresa.objects.all():
        writer.writerow([empresa.razao_social, empresa.cnpj])
        
    return response

@admin_required
def nova_empresa(request):
    return generico_form(request, EmpresaForm, 'contratos/portal/form_generico.html', 'Nova Empresa', 'listar_empresas')

@admin_required
def editar_empresa(request, pk):
    instance = get_object_or_404(Empresa, pk=pk)
    return generico_form(request, EmpresaForm, 'contratos/portal/form_generico.html', f'Editar {instance}', 'listar_empresas', instance)

# --- CONTRATOS ---
@auditor_required
def listar_contratos(request):
    # Added 'objeto' and split company/cnpj for the generic list template to handle
    return generico_listar(
        request, Contrato, 'contratos/portal/lista_generica.html', 'Contratos', 
        'novo_contrato', 'editar_contrato',
        [('numero', 'Número'), ('tipo', 'Tipo'), ('empresa', 'Empresa'), ('cnpj', 'CNPJ'), ('objeto', 'Objeto'), ('vigencia_fim', 'Vigência')],
        url_exportar='exportar_contratos_csv',
        arquivo_exportacao='contratos.csv'
    )

@auditor_required
def exportar_contratos_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="contratos.csv"'
    response.write('\ufeff')  # BOM
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Número', 'Objeto', 'Empresa', 'CNPJ', 'Início Vigência', 'Fim Vigência', 'Valor Total'])
    
    for contrato in Contrato.objects.select_related('empresa').all():
        writer.writerow([
            contrato.numero, 
            contrato.objeto, 
            contrato.empresa.razao_social, 
            contrato.empresa.cnpj, 
            contrato.vigencia_inicio.strftime('%d/%m/%Y'), 
            contrato.vigencia_fim.strftime('%d/%m/%Y'),
            str(contrato.valor_total).replace('.', ',')
        ])
    
    return response

@auditor_required
def detalhe_contrato(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)

    comissoes_ativas = contrato.comissoes.filter(ativa=True).prefetch_related(
        Prefetch(
            'integrantes',
            queryset=_get_integrantes_ordenados(),
            to_attr='integrantes_lista'
        )
    )

    comissoes_fiscalizacao = [c for c in comissoes_ativas if c.tipo == 'FISCALIZACAO']
    comissoes_recebimento = [c for c in comissoes_ativas if c.tipo == 'RECEBIMENTO']

    return render(request, 'contratos/portal/detalhe_contrato.html', {
        'contrato': contrato,
        'comissoes_fiscalizacao': comissoes_fiscalizacao,
        'comissoes_recebimento': comissoes_recebimento
    })

@admin_required
def novo_contrato(request):
    return generico_form(request, ContratoForm, 'contratos/portal/form_generico.html', 'Novo Contrato', 'listar_contratos')

@admin_required
def editar_contrato(request, pk):
    instance = get_object_or_404(Contrato, pk=pk)
    return generico_form(request, ContratoForm, 'contratos/portal/form_generico.html', f'Editar {instance}', 'listar_contratos', instance)

# --- AGENTES ---
@auditor_required
def listar_agentes(request):
    return generico_listar(
        request, Agente, 'contratos/portal/lista_generica.html', 'Agentes', 
        'novo_agente', 'editar_agente',
        [('posto', 'Posto'), ('nome_de_guerra', 'Nome de Guerra'), ('saram', 'SARAM'), ('cpf', 'CPF')],
        url_exportar='exportar_agentes_csv',
        arquivo_exportacao='agentes.csv'
    )

@auditor_required
def exportar_agentes_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="agentes.csv"'
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Posto', 'Nome de Guerra', 'Nome Completo', 'SARAM', 'CPF', 'Data Último Curso'])
    
    for agente in Agente.objects.select_related('posto').all():
        writer.writerow([
            agente.posto.sigla, 
            agente.nome_de_guerra, 
            agente.nome_completo, 
            agente.saram,
            agente.cpf if agente.cpf else '',
            agente.data_ultimo_curso.strftime('%d/%m/%Y') if agente.data_ultimo_curso else ''
        ])
    
    return response

@admin_required
def novo_agente(request):
    return generico_form(request, AgenteForm, 'contratos/portal/form_generico.html', 'Novo Agente', 'listar_agentes')

@admin_required
def editar_agente(request, pk):
    instance = get_object_or_404(Agente, pk=pk)
    return generico_form(request, AgenteForm, 'contratos/portal/form_generico.html', f'Editar {instance}', 'listar_agentes', instance)

# --- COMISSÕES ---
@auditor_required
def listar_comissoes(request):
    return generico_listar(
        request, Comissao, 'contratos/portal/lista_generica.html', 'Comissões', 
        'nova_comissao', 'editar_comissao',
        [('id', 'Nº'), ('contrato', 'Contrato'), ('tipo', 'Tipo'), ('ativa', 'Ativa?')],
        url_exportar='exportar_comissoes_csv',
        arquivo_exportacao='comissoes.csv'
    )

@auditor_required
def exportar_comissoes_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="comissoes.csv"'
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Nº', 'Contrato', 'Empresa', 'Tipo', 'Ativa', 'Portaria Nº', 'Portaria Data', 'Boletim Nº', 'Boletim Data', 'Início', 'Fim'])
    
    for comissao in Comissao.objects.select_related('contrato__empresa').all():
        writer.writerow([
            comissao.id,
            comissao.contrato.numero,
            comissao.contrato.empresa.razao_social,
            comissao.get_tipo_display(),
            'Sim' if comissao.ativa else 'Não',
            comissao.portaria_numero or '',
            comissao.portaria_data.strftime('%d/%m/%Y') if comissao.portaria_data else '',
            comissao.boletim_numero or '',
            comissao.boletim_data.strftime('%d/%m/%Y') if comissao.boletim_data else '',
            comissao.data_inicio.strftime('%d/%m/%Y') if comissao.data_inicio else '',
            comissao.data_fim.strftime('%d/%m/%Y') if comissao.data_fim else ''
        ])
    
    return response

@admin_required
def nova_comissao(request):
    if request.method == 'POST':
        form = ComissaoForm(request.POST)
        if form.is_valid():
            comissao = form.save()
            messages.success(request, 'Comissão criada! Agora adicione os integrantes.')
            # Redireciona para EDIÇÃO para forçar adição de membros
            return redirect('editar_comissao', pk=comissao.pk)
    else:
        form = ComissaoForm()
    
    return render(request, 'contratos/portal/detalhe_comissao.html', {
        'form': form,
        'titulo': 'Nova Comissão'
    })

@admin_required
def editar_comissao(request, pk):
    instance = get_object_or_404(Comissao, pk=pk)
    
    # Custom logic for Master-Detail view
    if request.method == 'POST':
        form = ComissaoForm(request.POST, instance=instance)
        if form.is_valid():
            # Validação: Impedir ativar sem membros
            comissao = form.save(commit=False)
            if comissao.ativa and instance.integrantes.count() == 0:
                messages.error(request, '🚫 A comissão não pode ser ativada sem integrantes.')
                comissao.ativa = False # Força inativa
                comissao.save()
            else:
                comissao.save()
                messages.success(request, 'Comissão salva com sucesso!')
            return redirect('editar_comissao', pk=instance.pk) # Maintain user on same page
    else:
        form = ComissaoForm(instance=instance)
    
    context = {
        'form': form,
        'object': instance,
        'titulo': f'Editar {instance}',
        'designacoes': _get_integrantes_ordenados().filter(comissao=instance)
    }
    return render(request, 'contratos/portal/detalhe_comissao.html', context)

# --- DESIGNAÇÕES (Vinculadas a Comissão) ---

@admin_required
def nova_designacao_comissao(request, comissao_id):
    comissao = get_object_or_404(Comissao, pk=comissao_id)
    
    # Pre-fill data from Commission
    initial_data = {
        'comissao': comissao,
        'portaria_numero': comissao.portaria_numero,
        'portaria_data': comissao.portaria_data,
        'boletim_numero': comissao.boletim_numero,
        'boletim_data': comissao.boletim_data,
        'data_inicio': comissao.data_inicio,
        'data_fim': comissao.data_fim
    }
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data['comissao'] = comissao.id
        form = IntegranteForm(post_data)
        if form.is_valid():
            form.save()
            messages.success(request, 'Integrante adicionado com sucesso!')
            return redirect('editar_comissao', pk=comissao.pk)
    else:
        form = IntegranteForm(initial=initial_data)
        # Lock commission field
        form.fields['comissao'].widget.attrs['disabled'] = 'disabled'
        form.fields['comissao'].initial = comissao
    
    return render(request, 'contratos/portal/form_generico.html', {
        'form': form,
        'titulo': f'Nova Designação ({comissao.contrato.numero})'
    })

@admin_required
def editar_designacao_comissao(request, pk):
    instance = get_object_or_404(Integrante, pk=pk)
    comissao = instance.comissao
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data['comissao'] = comissao.id
        form = IntegranteForm(post_data, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Designação atualizada com sucesso!')
            return redirect('editar_comissao', pk=comissao.pk)
    else:
        form = IntegranteForm(instance=instance)
        # Lock commission field
        form.fields['comissao'].widget.attrs['disabled'] = 'disabled'

    return render(request, 'contratos/portal/form_generico.html', {
        'form': form,
        'titulo': 'Editar Designação'
    })

# --- OLD (REMOVER) ---
@login_required
def listar_designacoes(request):
    # Designações precisam de um tratamento um pouco especial na listagem para mostrar infos cruzadas, mas vamos tentar manter genérico
    # Para o template genérico funcionar com objetos relacionados, ele precisa de acesso simples
    # Vamos fazer algo customizado:
    items = Integrante.objects.select_related('comissao__contrato', 'agente', 'funcao').all()
    context = {
        'items': items,
        'titulo': 'Designações',
        'url_novo': 'nova_designacao',
        'url_editar': 'editar_designacao',
        'custom_cols': ['Contrato', 'Militar', 'Função', 'Início', 'Fim'],
        'is_designacao': True
    }
    return render(request, 'contratos/portal/lista_generica.html', context)

@login_required
def nova_designacao(request):
    return generico_form(request, IntegranteForm, 'contratos/portal/form_generico.html', 'Nova Designação', 'listar_designacoes')

@login_required
def editar_designacao(request, pk):
    instance = get_object_or_404(Integrante, pk=pk)
    return generico_form(request, IntegranteForm, 'contratos/portal/form_generico.html', 'Editar Designação', 'listar_designacoes', instance)
@admin_required
def reordenar_integrantes(request):
    """
    Recebe um POST com uma lista de IDs de integrantes e atualiza a ordem deles.
    Esperado JSON: {'ordem': [id1, id2, id3, ...]}
    """
    import json
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lista_ids = data.get('ordem', [])
            
            for index, integrante_id in enumerate(lista_ids):
                # Usar update para ser mais rápido e evitar sinais desnecessários se houver
                Integrante.objects.filter(pk=integrante_id).update(ordem=index + 1)
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método inválido'}, status=405)
