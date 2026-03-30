from django.test import Client

client = Client()
client.login(username='auditor', password='senha123')
client.login(username='auditor', password='senha123')

urls = [
    '/auditoria/exportar/',
    '/auditoria/vencimentos/csv/',
    '/auditoria/qualificacao/csv/',
    '/auditoria/relatorio/periodo/csv/?data_inicial=2026-01-01&data_final=2026-12-31'
]

for url in urls:
    response = client.get(url, HTTP_HOST='localhost')
    print(f"\nScanning: {url}")
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    print("-" * 50)
