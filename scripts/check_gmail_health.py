"""
Script de health check para Gmail API
Use em monitoramento (cron, Kubernetes, etc.)
"""
import sys
import os
import json
from datetime import datetime

# Adiciona o diretório base ao sys.path para importar módulos do Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from contratos.utils_gmail import gmail_client, GmailAPIError

def check_health():
    """Verifica se a Gmail API está funcionando"""
    resultado = {
        'timestamp': datetime.now().isoformat(),
        'status': 'ok',
        'detalhes': {}
    }
    
    try:
        # Tenta autenticar
        gmail_client.autenticar()
        resultado['detalhes']['autenticacao'] = 'ok'
        
        # Verifica validade do token
        creds = gmail_client._service._http.credentials
        if creds.expired:
            resultado['detalhes']['token'] = 'expirado'
            resultado['status'] = 'warning'
        else:
            resultado['detalhes']['token'] = 'valido'
            
    except GmailAPIError as e:
        resultado['status'] = 'error'
        resultado['detalhes']['erro'] = str(e)
    
    print(json.dumps(resultado, indent=2))
    
    # Código de saída para scripts
    if resultado['status'] == 'error':
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    check_health()
