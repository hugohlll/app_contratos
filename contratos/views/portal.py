from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from contratos.utils import admin_required, auditor_required
from django.contrib import messages
from django.contrib import messages
from django.urls import reverse
from ..models import Empresa, Contrato, Agente, Integrante, Comissao
from ..forms import EmpresaForm, ContratoForm, AgenteForm, IntegranteForm, ComissaoForm

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

def generico_listar(request, model, template_name, titulo, url_novo, url_editar, fields_display):
    items = model.objects.all()
    context = {
        'items': items,
        'titulo': titulo,
        'url_novo': url_novo,
        'url_editar': url_editar,
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

# --- EMPRESAS ---
@auditor_required
def listar_empresas(request):
    return generico_listar(
        request, Empresa, 'contratos/portal/lista_generica.html', 'Empresas', 
        'nova_empresa', 'editar_empresa', 
        [('razao_social', 'Razão Social'), ('cnpj', 'CNPJ'), ('contato', 'Contato')]
    )

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
    return generico_listar(
        request, Contrato, 'contratos/portal/lista_generica.html', 'Contratos', 
        'novo_contrato', 'editar_contrato',
        [('numero', 'Número'), ('empresa', 'Empresa'), ('vigencia_fim', 'Vigência')]
    )

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
        [('posto', 'Posto'), ('nome_de_guerra', 'Nome de Guerra'), ('saram', 'SARAM')]
    )

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
        [('contrato', 'Contrato'), ('tipo', 'Tipo'), ('ativa', 'Ativa?')]
    )

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
        'designacoes': instance.integrantes.all().select_related('agente', 'funcao')
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
        form = IntegranteForm(request.POST)
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
        form = IntegranteForm(request.POST, instance=instance)
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
