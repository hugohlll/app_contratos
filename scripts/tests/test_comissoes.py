import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from contratos.models import Comissao, Integrante

hoje = date.today()

print("HOJE:", hoje)

print("\n--- Comissões Inativas que deveriam ser ativadas ---")
qs_ativar = Comissao.objects.filter(ativa=False, data_inicio__lte=hoje).exclude(data_fim__lt=hoje)
print(f"Total: {qs_ativar.count()}")
for c in qs_ativar:
    print(f"ID: {c.id}, Contrato: {c.contrato.numero}, Inicio: {c.data_inicio}, Fim: {c.data_fim}, Ativa: {c.ativa}")

print("\n--- Comissões Ativas que deveriam ser desativadas ---")
qs_desativar = Comissao.objects.filter(ativa=True, data_fim__lt=hoje)
print(f"Total: {qs_desativar.count()}")
for c in qs_desativar:
    print(f"ID: {c.id}, Contrato: {c.contrato.numero}, Inicio: {c.data_inicio}, Fim: {c.data_fim}, Ativa: {c.ativa}")

print("\n--- Todas as Comissões com data_fim em branco ---")
qs_blank = Comissao.objects.filter(data_fim__isnull=True)
print(f"Total: {qs_blank.count()}")
for c in qs_blank:
    print(f"ID: {c.id}, Contrato: {c.contrato.numero}, Inicio: {c.data_inicio}, Ativa: {c.ativa}")

print("\n--- Integrantes de comissões com data_fim expirada que não tiveram data_fim atualizada ---")
for c in Comissao.objects.filter(data_fim__lt=hoje):
    integrantes = c.integrantes.filter(data_fim__gt=c.data_fim)
    if integrantes.exists():
        print(f"Comissão ID {c.id} (Fim: {c.data_fim}) tem integrantes com data_fim maior:")
        for i in integrantes:
            print(f"  Integrante ID {i.id}, Fim: {i.data_fim}")
