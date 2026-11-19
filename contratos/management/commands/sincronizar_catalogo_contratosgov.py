from django.core.management.base import BaseCommand, CommandError

from contratos.services.contratosgov import ClienteContratosGov, ContratosGovErro
from contratos.services.om_beneficiada import ClassificacaoErro, avisar_novos, sincronizar_catalogo


class Command(BaseCommand):
    help = (
        'Atualiza o catálogo de contratos da UG com a lista do Contratos.gov.br (#51): grava os contratos '
        'novos como "a classificar", vincula os que já existem no SISCONT e recalcula a sugestão de OM '
        'beneficiada dos pendentes. Falha na leitura da lista não altera nenhum dado.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--sem-sugestao', action='store_true',
                            help='Não consulta os detalhes dos pendentes para recalcular a sugestão')
        parser.add_argument('--sem-email', action='store_true',
                            help='Não envia o aviso de contratos novos a classificar')

    def handle(self, *args, **options):
        try:
            resultado = sincronizar_catalogo(ClienteContratosGov(), sugestoes=not options['sem_sugestao'])
        except (ContratosGovErro, ClassificacaoErro) as e:
            raise CommandError(f'Catálogo não atualizado: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'Lista lida: {resultado.lidos} registro(s); {resultado.no_catalogo} no catálogo.'))
        self.stdout.write(f'Novos a classificar: {len(resultado.novos)}')
        self.stdout.write(f'Vinculados automaticamente (já no SISCONT): {len(resultado.vinculados)}')
        if not options['sem_sugestao']:
            self.stdout.write(f'Sugestões recalculadas: {resultado.sugestoes}'
                              + (f' ({resultado.sugestoes_falhas} com falha na consulta)'
                                 if resultado.sugestoes_falhas else ''))
        self.stdout.write(f'Total a classificar: {resultado.pendentes}')
        if resultado.novos and not options['sem_email']:
            if avisar_novos(resultado.novos):
                self.stdout.write('Aviso enfileirado para os Administradores.')
