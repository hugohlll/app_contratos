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

# --- EXPORT HELPERS ---
import csv
import urllib.parse
from django.http import HttpResponse

def export_csv_or_xlsx(request, filename_base, headers, data_rows):
    """
    Gera um arquivo XLSX ou CSV com base em '?formato=xlsx|csv'.
    :param request: Django HttpRequest.
    :param filename_base: String com o nome base ('empresas'). A extensão será adicionada via lógica.
    :param headers: Lista com o texto das colunas.
    :param data_rows: Lista/Generator contendo as colunas em ordem para cada linha.
    """
    formato = request.GET.get('formato', 'csv')
    
    if formato == 'xlsx':
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        for row in data_rows:
            # openpyxl lida bem com tipos embutidos, converte strings formatadas
            ws.append([str(i) if i is not None else '' for i in row])
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        encoded_filename = urllib.parse.quote(f"{filename_base}.xlsx")
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"; filename*=UTF-8\'\'{encoded_filename}'
        wb.save(response)
        return response
    
    # CSV Padrão (UTF-8 com BOM)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    encoded_filename = urllib.parse.quote(f"{filename_base}.csv")
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    response.write(b'\xef\xbb\xbf')
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(headers)
    for row in data_rows:
        writer.writerow(row)
        
    return response