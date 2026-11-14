from django.core.management.base import BaseCommand

from contratos.services import email as servico_email


class Command(BaseCommand):
    help = 'Envia os e-mails pendentes da fila e apaga os enviados há mais de 90 dias.'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=50, help='Máximo de e-mails por execução')

    def handle(self, *args, **options):
        enviados, falhas = servico_email.processar_fila(limite=options['limite'])
        apagados = servico_email.limpar_antigos()
        # Silencioso quando não há nada a fazer, para não encher o log do cron a cada 2 minutos.
        if enviados or falhas or apagados:
            self.stdout.write(f'Fila de e-mails: {enviados} enviado(s), {falhas} falha(s), '
                              f'{apagados} registro(s) antigo(s) apagado(s).')
