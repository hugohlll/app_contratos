"""
Script para renovação manual do token
Use se a renovação automática falhar
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    print("=" * 60)
    print("RENOVAÇÃO DE TOKEN - GMAIL API")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_path = os.path.join(base_dir, 'secrets', 'token.json')
    creds_path = os.path.join(base_dir, 'secrets', 'credentials.json')
    
    # Fallback se não estiver na pasta secrets
    if not os.path.exists(token_path):
        token_path = os.path.join(base_dir, 'token.json')
    if not os.path.exists(creds_path):
        creds_path = os.path.join(base_dir, 'credentials.json')
    
    # Tenta renovar token existente
    if os.path.exists(token_path):
        print("\nTentando renovar token existente...")
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
                print("✅ Token renovado com sucesso!")
                return
            except Exception as e:
                print(f"❌ Falha na renovação: {e}")
        else:
            print("Token não pode ser renovado automaticamente. Gerando novo token...")
            
    if not os.path.exists(creds_path):
        print(f"❌ Erro: credentials.json não encontrado em {creds_path}")
        return
        
    # Gera novo token
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    
    print("✅ Novo token gerado e salvo com sucesso!")

if __name__ == '__main__':
    main()
