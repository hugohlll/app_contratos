import getpass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from contratos.services.contratosgov import (
    ClienteContratosGov, ContratosGovErro, ProxyAutenticacaoErro,
)


class Command(BaseCommand):
    help = (
        'Testa o acesso à API do Contratos.gov.br pelo proxy configurado (CONTRATOSGOV_*) '
        'e lista os contratos ativos da UG. Somente leitura; nada é gravado no banco.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--ug', default=settings.CONTRATOSGOV_UG,
                            help=f'UG a consultar (padrão: {settings.CONTRATOSGOV_UG})')
        parser.add_argument('--proxy', default=None,
                            help='Proxy a usar só neste teste, ex.: http://proxy-brasilia.intraer:8080')
        parser.add_argument('--sem-proxy', action='store_true',
                            help='Ignora o proxy configurado e conecta direto')
        parser.add_argument('--usuario', default=None,
                            help='Usuário do proxy só neste teste (a senha será pedida no teclado)')
        parser.add_argument('--pedir-senha', action='store_true',
                            help='Pede a senha do proxy no teclado (não aparece e não é gravada)')
        parser.add_argument('--limite', type=int, default=10,
                            help='Quantos contratos mostrar (padrão: 10)')

    def handle(self, *args, **options):
        proxy = '' if options['sem_proxy'] else options['proxy']
        usuario = options['usuario']
        senha = None
        if usuario is not None or options['pedir_senha']:
            if usuario is None:
                usuario = settings.CONTRATOSGOV_PROXY_USUARIO or input('Usuário do proxy: ')
            senha = getpass.getpass('Senha do proxy (não aparece): ')

        try:
            cliente = ClienteContratosGov(proxy=proxy, usuario=usuario, senha=senha)
        except ContratosGovErro as e:
            raise CommandError(str(e))

        self.stdout.write(f'API:   {cliente.base_url}')
        self.stdout.write(f'Proxy: {cliente.descricao_proxy()}')
        self.stdout.write(f'UG:    {options["ug"]}')

        try:
            contratos = cliente.contratos_ativos(options['ug'])
        except ProxyAutenticacaoErro as e:
            raise CommandError(f'{e}\nConfira usuário e senha do proxy.')
        except ContratosGovErro as e:
            raise CommandError(str(e))

        if not isinstance(contratos, list):
            raise CommandError(f'Resposta inesperada (esperava uma lista): {str(contratos)[:200]}')

        self.stdout.write(self.style.SUCCESS(
            f'Conexão OK: {len(contratos)} contrato(s) ativo(s) na UG {options["ug"]}.'))
        for c in contratos[:options['limite']]:
            fornecedor = (c.get('fornecedor') or {}).get('nome', '')
            self.stdout.write(
                f'  id {c.get("id")} | {c.get("numero")} | {c.get("vigencia_fim") or "-"} | '
                f'{fornecedor[:50]}'
            )
        if len(contratos) > options['limite']:
            self.stdout.write(f'  ... e mais {len(contratos) - options["limite"]}.')
