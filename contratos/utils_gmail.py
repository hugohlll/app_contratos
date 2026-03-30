"""
Módulo utilitário para envio de e-mails via Gmail API
"""
import os
import base64
import logging
from email.message import EmailMessage
from django.conf import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class GmailAPIClient:
    """Cliente para envio de e-mails via Gmail API"""
    
    def __init__(self):
        self.credentials_path = getattr(
            settings, 
            'GMAIL_CREDENTIALS_PATH', 
            os.path.join(settings.BASE_DIR, 'credentials.json')
        )
        self.token_path = getattr(
            settings, 
            'GMAIL_TOKEN_PATH', 
            os.path.join(settings.BASE_DIR, 'token.json')
        )
        self._service = None
    
    def autenticar(self):
        """Autentica e retorna serviço Gmail"""
        if self._service:
            return self._service
            
        creds = None
        
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(
                self.token_path, 
                SCOPES
            )
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Salva token renovado
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Falha ao renovar token: {e}")
                    raise
            else:
                raise RuntimeError(
                    "Token inválido. É necessário reautenticar manualmente."
                )
        
        self._service = build('gmail', 'v1', credentials=creds)
        return self._service
    
    def enviar_email(self, destinatario, assunto, mensagem, remetente=None):
        """
        Envia um e-mail
        
        Args:
            destinatario: E-mail do destinatário
            assunto: Assunto do e-mail
            mensagem: Corpo do e-mail (texto puro)
            remetente: E-mail do remetente (opcional)
        
        Returns:
            dict: {'status': 'sucesso', 'id_mensagem': '...'}
        
        Raises:
            GmailAPIError: Em caso de falha no envio
        """
        try:
            service = self.autenticar()
            
            email_msg = EmailMessage()
            email_msg.set_content(mensagem)
            email_msg['To'] = destinatario
            email_msg['From'] = remetente or settings.EMAIL_PADRAO
            email_msg['Subject'] = assunto
            
            encoded_message = base64.urlsafe_b64encode(
                email_msg.as_bytes()
            ).decode()
            
            response = service.users().messages().send(
                userId="me", 
                body={'raw': encoded_message}
            ).execute()
            
            logger.info(f"E-mail enviado para {destinatario}. ID: {response['id']}")
            
            return {
                'status': 'sucesso',
                'id_mensagem': response['id']
            }
            
        except HttpError as error:
            logger.error(f"Erro na Gmail API: {error}")
            raise GmailAPIError(f"Erro na API: {error}")
        except Exception as e:
            logger.error(f"Erro inesperado: {e}")
            raise GmailAPIError(f"Erro inesperado: {e}")
    
    def enviar_email_html(self, destinatario, assunto, texto, html, remetente=None):
        """
        Envia e-mail com versão HTML e texto puro
        """
        try:
            service = self.autenticar()
            
            email_msg = EmailMessage()
            email_msg.set_alternatives(
                [(texto, 'plain'), (html, 'html')]
            )
            email_msg['To'] = destinatario
            email_msg['From'] = remetente or settings.EMAIL_PADRAO
            email_msg['Subject'] = assunto
            
            encoded_message = base64.urlsafe_b64encode(
                email_msg.as_bytes()
            ).decode()
            
            response = service.users().messages().send(
                userId="me", 
                body={'raw': encoded_message}
            ).execute()
            
            logger.info(f"E-mail HTML enviado para {destinatario}. ID: {response['id']}")
            
            return {
                'status': 'sucesso',
                'id_mensagem': response['id']
            }
            
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail HTML: {e}")
            raise GmailAPIError(f"Erro ao enviar e-mail HTML: {e}")


class GmailAPIError(Exception):
    """Exceção personalizada para erros da Gmail API"""
    pass


# Instância singleton para reutilização
gmail_client = GmailAPIClient()
