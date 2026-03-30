"""
Script de teste para envio de e-mails via Gmail API
Simula cenário real de produção com parâmetros personalizáveis
"""
import os
import sys
import base64
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def autenticar_gmail():
    """Autentica usando credentials.json e token.json existentes"""
    creds = None
    
    # Verifica caminho absoluto dentro do container
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, 'token.json')
    credentials_path = os.path.join(base_dir, 'credentials.json')
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return creds

def enviar_email(destinatario, assunto, mensagem_texto, remetente=None):
    """
    Envia um e-mail usando a Gmail API
    
    Args:
        destinatario: E-mail do destinatário
        assunto: Assunto do e-mail
        mensagem_texto: Corpo do e-mail
        remetente: E-mail do remetente (padrão: hugohlllima@gmail.com)
    
    Returns:
        dict: Resultado do envio com status e ID da mensagem ou erro
    """
    try:
        creds = autenticar_gmail()
        service = build('gmail', 'v1', credentials=creds)

        mensagem = EmailMessage()
        mensagem.set_content(mensagem_texto)

        # Define remetente padrão se não fornecido
        if remetente is None:
            remetente = 'hugohlllima@gmail.com'
        
        mensagem['To'] = destinatario
        mensagem['From'] = remetente
        mensagem['Subject'] = assunto

        encoded_message = base64.urlsafe_b64encode(mensagem.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        send_message = service.users().messages().send(userId="me", body=create_message).execute()

        return {
            'status': 'sucesso',
            'id_mensagem': send_message['id']
        }

    except HttpError as error:
        return {
            'status': 'erro_api',
            'detalhe': f"Ocorreu um erro na API: {error}"
        }
    except Exception as e:
        return {
            'status': 'erro_inesperado',
            'detalhe': f"Erro inesperado: {e}"
        }

def testar_cenario_producao():
    """Executa testes simulando cenários reais de produção"""
    print("=" * 60)
    print("TESTE DE ENVIO DE E-MAIL - CENÁRIO PRODUÇÃO")
    print("=" * 60)
    
    # Cenário 1: Notificação de vencimento de contrato
    print("\n[Cenário 1] Notificação de Vencimento de Contrato")
    resultado = enviar_email(
        destinatario='hugohlllima@gmail.com',
        assunto='[ALERTA] Vencimento de Contrato - 5 dias',
        mensagem_texto="""
Olá,

Este é um e-mail automático de notificação de vencimento de contrato.

Contrato: 001/2024
Fornecedor: Empresa XYZ Ltda
Valor: R$ 50.000,00
Vencimento: 05/04/2026

Atenção: O contrato vencerá em 5 dias úteis.

Atenciosamente,
Sistema de Gestão de Contratos
        """
    )
    print(f"Status: {resultado['status']}")
    if resultado['status'] == 'sucesso':
        print(f"ID da mensagem: {resultado['id_mensagem']}")
    else:
        print(f"Detalhe: {resultado['detalhe']}")
    
    # Cenário 2: Notificação de expiração de contrato
    print("\n[Cenário 2] Notificação de Contrato Expirado")
    resultado = enviar_email(
        destinatario='hugohlllima@gmail.com',
        assunto='[URGENTE] Contrato Expirado - Ação Necessária',
        mensagem_texto="""
Olá,

Este é um e-mail automático de alerta de contrato expirado.

Contrato: 002/2024
Fornecedor: ABC Serviços S.A.
Valor: R$ 120.000,00
Vencimento: 28/03/2026

AÇÃO NECESSÁRIA: O contrato está expirado. Regularize a situação.

Atenciosamente,
Sistema de Gestão de Contratos
        """
    )
    print(f"Status: {resultado['status']}")
    if resultado['status'] == 'sucesso':
        print(f"ID da mensagem: {resultado['id_mensagem']}")
    else:
        print(f"Detalhe: {resultado['detalhe']}")
    
    # Cenário 3: Relatório semanal
    print("\n[Cenário 3] Relatório Semanal de Contratos")
    resultado = enviar_email(
        destinatario='hugohlllima@gmail.com',
        assunto='[RELATÓRIO] Status Semanal de Contratos - 30/03/2026',
        mensagem_texto="""
Olá,

Segue o relatório semanal de status dos contratos:

RESUMO:
- Contratos Ativos: 45
- Contratos Vencendo (30 dias): 8
- Contratos Expirados: 2
- Contratos Renovados: 3

Para mais detalhes, acesse o painel de auditoria.

Atenciosamente,
Sistema de Gestão de Contratos
        """
    )
    print(f"Status: {resultado['status']}")
    if resultado['status'] == 'sucesso':
        print(f"ID da mensagem: {resultado['id_mensagem']}")
    else:
        print(f"Detalhe: {resultado['detalhe']}")
    
    print("\n" + "=" * 60)
    print("TESTES CONCLUÍDOS")
    print("=" * 60)

if __name__ == '__main__':
    testar_cenario_producao()
