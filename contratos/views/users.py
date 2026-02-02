from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from contratos.utils import admin_required, is_admin

@admin_required
def listar_usuarios(request):
    usuarios = User.objects.all().order_by('username')
    # Annotate with role for display
    for u in usuarios:
        if u.is_superuser:
            u.perfil_display = "Superusuário"
        elif u.groups.filter(name='Administradores').exists():
            u.perfil_display = "Administrador"
        elif u.groups.filter(name='Auditores').exists():
            u.perfil_display = "Auditor"
        else:
            u.perfil_display = "Sem Perfil"
            
    return render(request, 'contratos/portal/users/lista.html', {
        'usuarios': usuarios,
        'titulo': 'Gerenciar Usuários'
    })

@admin_required
def novo_usuario(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        perfil = request.POST.get('perfil') # 'admin' or 'auditor'

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuário já existe.')
            return redirect('novo_usuario')

        user = User.objects.create_user(username=username, email=email, password=password)
        
        # Assign Group
        update_user_group(user, perfil)
        
        messages.success(request, 'Usuário criado com sucesso!')
        return redirect('listar_usuarios')

    return render(request, 'contratos/portal/users/form.html', {
        'titulo': 'Novo Usuário',
        'is_new': True
    })

@admin_required
def editar_usuario(request, pk):
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        user.email = request.POST.get('email')
        perfil = request.POST.get('perfil')
        
        # Password update only if provided
        new_password = request.POST.get('password')
        if new_password:
            user.set_password(new_password)
            
        user.save()
        update_user_group(user, perfil)
        
        messages.success(request, 'Usuário atualizado com sucesso!')
        return redirect('listar_usuarios')

    # Determine current profile
    current_perfil = 'none'
    if user.groups.filter(name='Administradores').exists():
        current_perfil = 'admin'
    elif user.groups.filter(name='Auditores').exists():
        current_perfil = 'auditor'

    return render(request, 'contratos/portal/users/form.html', {
        'titulo': f'Editar Usuário: {user.username}',
        'usuario': user,
        'current_perfil': current_perfil,
        'is_new': False
    })

@admin_required
def excluir_usuario(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if user.is_superuser:
            messages.error(request, 'Não é possível excluir superusuários por aqui.')
        else:
            user.delete()
            messages.success(request, 'Usuário excluído.')
        return redirect('listar_usuarios')
    
    return render(request, 'contratos/portal/users/delete_confirm.html', {'usuario': user})

@login_required
def alterar_senha(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Sua senha foi alterada com sucesso!')
            return redirect('portal_home')
        else:
            messages.error(request, 'Por favor, corrija o erro abaixo.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'contratos/portal/users/senha.html', {
        'form': form
    })

def update_user_group(user, perfil_code):
    # Ensure groups exist
    admin_group, _ = Group.objects.get_or_create(name='Administradores')
    auditor_group, _ = Group.objects.get_or_create(name='Auditores')
    
    user.groups.clear()
    
    if perfil_code == 'admin':
        user.groups.add(admin_group)
    elif perfil_code == 'auditor':
        user.groups.add(auditor_group)
