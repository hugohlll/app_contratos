from datetime import date
from django.db.models import Q

def get_filtro_ativos():
    """
    Retorna o objeto Q para filtrar apenas integrantes ativos.
    Regra: (Sem desligamento OU Desligamento Futuro) E (Sem fim previsto OU Fim previsto Futuro)
    """
    hoje = date.today()
    return (
        (Q(data_desligamento__isnull=True) | Q(data_desligamento__gt=hoje)) &
        (Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
    )

# --- PERMISSIONS ---
from django.contrib.auth.decorators import user_passes_test

def is_admin(user):
    """
    Check if user is in 'Administradores' group or is a superuser.
    """
    if not user.is_authenticated: return False
    return user.is_superuser or user.groups.filter(name='Administradores').exists()

def is_auditor(user):
    """
    Check if user is in 'Auditores' OR 'Administradores' group (Admins imply Audit).
    """
    if not user.is_authenticated: return False
    if is_admin(user): return True
    return user.groups.filter(name='Auditores').exists()

def admin_required(view_func):
    return user_passes_test(is_admin, login_url='portal_home')(view_func)

def auditor_required(view_func):
    return user_passes_test(is_auditor, login_url='pesquisa')(view_func)

# --- FORMATTERS ---
import re

def clean_digits(value):
    """Remove tudo que não for dígito."""
    if not value: return ""
    return re.sub(r'\D', '', str(value))

def format_cpf(value):
    """
    Formata CPF para: 000.000.000-00
    Espera receber apenas números (11 dígitos).
    """
    v = clean_digits(value)
    if len(v) != 11: return value
    return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"

def format_cnpj(value):
    """
    Formata CNPJ para: 00.000.000/0000-00
    Espera receber apenas números (14 dígitos).
    """
    v = clean_digits(value)
    if len(v) != 14: return value
    return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"