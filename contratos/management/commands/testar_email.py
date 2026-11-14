import smtplib

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from contratos.services import email as servico_email


class Command(BaseCommand):
    help = (
        'Envia um e-mail de teste pelo SMTP do Intraer. Por padrão passa pela fila '
        '(enfileira e processa na hora, como o cron faria); com --direto envia sem a fila.'
    )

    def add_arguments(self, parser):
        parser.add_argument('destinatario', help='E-mail que receberá o teste')
        parser.add_argument('--direto', action='store_true',
                            help='Envia direto pelo SMTP, sem passar pela fila (diagnóstico)')

    def handle(self, *args, **options):
        destinatario = options['destinatario']
        agora = timezone.localtime()
        assunto = f'[SISCONT] Teste de e-mail – {agora:%d/%m/%Y %H:%M}'
        texto = (
            'Este é um e-mail de teste do SISCONT.\n\n'
            f'Servidor: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}\n'
            f'Remetente: {settings.DEFAULT_FROM_EMAIL}\n'
            f'Modo: {"direto (sem fila)" if options["direto"] else "fila"}\n'
        )
        self.stdout.write(f'Backend: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'Servidor: {settings.EMAIL_HOST}:{settings.EMAIL_PORT} (usuário: '
                          f'{settings.EMAIL_HOST_USER or "-"})')

        if options['direto']:
            try:
                servico_email.enviar_agora([destinatario], assunto, texto)
            except smtplib.SMTPResponseException as e:
                raise CommandError(f'Servidor respondeu {e.smtp_code}: '
                                   f'{e.smtp_error.decode(errors="replace")}')
            except Exception as e:
                raise CommandError(f'Falha no envio direto: {type(e).__name__}: {e}')
            self.stdout.write(self.style.SUCCESS(f'E-mail enviado direto para {destinatario}.'))
            return

        item = servico_email.enfileirar([destinatario], assunto, texto, categoria='TESTE')
        self.stdout.write(f'E-mail #{item.pk} colocado na fila. Processando a fila agora...')
        servico_email.processar_fila()
        item.refresh_from_db()
        if item.status == item.STATUS_ENVIADO:
            self.stdout.write(self.style.SUCCESS(f'E-mail #{item.pk} enviado para {destinatario}.'))
        else:
            raise CommandError(
                f'E-mail #{item.pk} não foi enviado ({item.get_status_display()}, tentativa '
                f'{item.tentativas}): {item.ultimo_erro}. O cron tentará de novo automaticamente.'
            )
