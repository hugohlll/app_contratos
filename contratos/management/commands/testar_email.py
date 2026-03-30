from django.core.management.base import BaseCommand
from contratos.utils_gmail import gmail_client, GmailAPIError

class Command(BaseCommand):
    help = 'Testa envio de e-mail via Gmail API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destinatario',
            type=str,
            help='E-mail do destinatário para teste'
        )

    def handle(self, *args, **options):
        destinatario = options.get('destinatario') or 'teste@suaempresa.com.br'
        
        self.stdout.write(f'Enviando e-mail de teste para {destinatario}...')
        
        try:
            resultado = gmail_client.enviar_email(
                destinatario=destinatario,
                assunto='[TESTE] Gmail API - Produção',
                mensagem='Este é um e-mail de teste da integração com Gmail API.'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f"✓ E-mail enviado com sucesso! ID: {resultado['id_mensagem']}")
            )
            
        except GmailAPIError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Erro ao enviar e-mail: {e}")
            )
