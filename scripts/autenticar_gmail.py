"""
Script para gerar token.json inicial
Execute APENAS uma vez em máquina com navegador
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    print("=" * 60)
    print("AUTENTICAÇÃO GMAIL API - GERAÇÃO DE TOKEN")
    print("=" * 60)
    
    # Verifica se credentials.json existe na pasta atual ou root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cred_paths = [
        'credentials.json',
        os.path.join(base_dir, 'credentials.json'),
        os.path.join(base_dir, 'secrets', 'credentials.json')
    ]
    
    cred_file = None
    for path in cred_paths:
        if os.path.exists(path):
            cred_file = path
            break
            
    if not cred_file:
        print("❌ Erro: credentials.json não encontrado!")
        print("Baixe o arquivo do Google Cloud Console e coloque na pasta secrets/.")
        return
    
    print("\n1. Abrindo navegador para autenticação...")
    print("2. Faça login com a conta do Gmail corporativa")
    print("3. Conceda a permissão de envio de e-mails")
    print("4. O navegador mostrará 'The authentication flow has completed'")
    
    flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Salva token na raiz
    token_out = os.path.join(base_dir, 'token.json')
    with open(token_out, 'w') as token:
        token.write(creds.to_json())
    
    print("\n✅ Token gerado com sucesso!")
    print(f"📁 Arquivo salvo em: {token_out}")
    print("\nPróximos passos:")
    print("1. Mova credentials.json e token.json para a pasta secrets/ do servidor de produção")
    print("2. Reinicie o container Docker (docker compose restart web cron)")

if __name__ == '__main__':
    main()
