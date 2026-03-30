import os
import base64
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def autenticar_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
      
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
          
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
              
    return creds

def enviar_email_teste():
    try:
        creds = autenticar_gmail()
        service = build('gmail', 'v1', credentials=creds)

        mensagem = EmailMessage()
        mensagem.set_content('Olá! Este é um teste automatizado de envio de e-mail disparado via API.')
          
        mensagem['To'] = 'hugohlllima@gmail.com'
        mensagem['From'] = 'hugohlllima@gmail.com'
        mensagem['Subject'] = '[Teste] Validação de disparo via Gmail API'

        encoded_message = base64.urlsafe_b64encode(mensagem.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        send_message = service.users().messages().send(userId="me", body=create_message).execute()
          
        print(f"Sucesso! E-mail enviado. ID da mensagem: {send_message['id']}")

    except HttpError as error:
        print(f"Ocorreu um erro na API: {error}")
    except Exception as e:
        print(f"Erro inesperado: {e}")

if __name__ == '__main__':
    enviar_email_teste()
