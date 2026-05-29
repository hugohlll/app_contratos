from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import json

from contratos.models import Setor, CargoRegimental
from contratos.forms import SetorForm, CargoRegimentalForm
from contratos.utils import is_admin, is_auditor


@login_required
def cargos_regimentais(request):
    """Página principal de Cargos Regimentais com formulário e tabela."""
    pode_editar = is_admin(request.user) or is_auditor(request.user)

    if request.method == 'POST' and pode_editar:
        form = CargoRegimentalForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cargo regimental cadastrado com sucesso.")
            return redirect('cargos_regimentais')
    else:
        form = CargoRegimentalForm()

    cargos = CargoRegimental.objects.select_related(
        'setor', 'agente', 'agente__posto'
    ).all()

    setores = Setor.objects.all()

    context = {
        'form': form,
        'cargos': cargos,
        'setores': setores,
        'pode_editar': pode_editar,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'contratos/cargos_regimentais.html', context)


@login_required
def editar_cargo_regimental(request, pk):
    """Editar um cargo regimental existente."""
    if not (is_admin(request.user) or is_auditor(request.user)):
        messages.error(request, "Acesso não autorizado.")
        return redirect('cargos_regimentais')

    cargo = get_object_or_404(CargoRegimental, pk=pk)

    if request.method == 'POST':
        form = CargoRegimentalForm(request.POST, instance=cargo)
        if form.is_valid():
            form.save()
            messages.success(request, "Cargo regimental atualizado com sucesso.")
            return redirect('cargos_regimentais')
    else:
        form = CargoRegimentalForm(instance=cargo)

    context = {
        'form': form,
        'cargo': cargo,
        'editando': True,
    }
    return render(request, 'contratos/cargos_regimentais_form.html', context)


@login_required
def excluir_cargo_regimental(request, pk):
    """Excluir um cargo regimental."""
    if not is_admin(request.user):
        messages.error(request, "Apenas administradores podem excluir registros.")
        return redirect('cargos_regimentais')

    cargo = get_object_or_404(CargoRegimental, pk=pk)

    if request.method == 'POST':
        cargo.delete()
        messages.success(request, "Cargo regimental excluído com sucesso.")

    return redirect('cargos_regimentais')


@login_required
def novo_setor(request):
    """Criar um novo setor via formulário."""
    if not (is_admin(request.user) or is_auditor(request.user)):
        messages.error(request, "Acesso não autorizado.")
        return redirect('cargos_regimentais')

    if request.method == 'POST':
        form = SetorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Setor cadastrado com sucesso.")
            return redirect('cargos_regimentais')
    else:
        form = SetorForm()

    return render(request, 'contratos/portal/form_generico.html', {
        'titulo': 'Novo Setor',
        'form': form,
    })


@login_required
def excluir_setor(request, pk):
    """Excluir um setor com verificação de segurança."""
    if not is_admin(request.user):
        messages.error(request, "Apenas administradores podem excluir setores.")
        return redirect('cargos_regimentais')

    setor = get_object_or_404(Setor, pk=pk)

    # Verifica se existem cargos associados
    if setor.cargos.exists():
        messages.error(
            request, 
            f"Não é possível excluir o setor '{setor.nome}' porque ele possui cargos regimentais associados. Remova os cargos antes de excluir o setor."
        )
        return redirect('cargos_regimentais')

    if request.method == 'POST':
        setor.delete()
        messages.success(request, f"Setor '{setor.nome}' excluído com sucesso.")

    return redirect('cargos_regimentais')


@login_required
def reordenar_setores(request):
    """
    Atualiza a ordem de exibição dos setores baseado em drag and drop.
    """
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'message': 'Acesso não autorizado.'}, status=403)
        
    try:
        data = json.loads(request.body)
        setor_ids = data.get('setor_ids', [])
        
        for index, setor_id in enumerate(setor_ids):
            Setor.objects.filter(id=setor_id).update(ordem=index)
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


