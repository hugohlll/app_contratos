import urllib.request
import urllib.error

url = "http://localhost:8000/portal/contratos/exportar.csv"
# Login cookie sessionid é necessário. Vou tentar pegar os headers sem login primeiro, 
# mas se falhar (redirect para login), precisarei simular o login.
# O mais fácil é usar o client de teste do Django, que já tenho config.

import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import Client

c = Client()
logged = c.login(username='auditor', password='senha123')
print(f"Login succesful: {logged}")

response = c.get('/portal/contratos/exportar.csv')

print(f"Status Code: {response.status_code}")
print("--- Headers ---")
for key, value in response.headers.items():
    print(f"{key}: {value}")

print(f"Content-Disposition Raw: {response.get('Content-Disposition')}")
