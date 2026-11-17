"""Cliente da API do Contratos.gov.br: proxy com usuário e senha.

Os testes usam um proxy falso em 127.0.0.1 (nenhum acesso à internet) para conferir
exatamente o que o urllib envia ao proxy, inclusive com senha cheia de caracteres especiais.
"""
import base64
import json
import os
import socketserver
import tempfile
import threading
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from contratos.services.contratosgov import (
    ClienteContratosGov, ContratosGovErro, ProxyAutenticacaoErro, RespostaHTTPErro,
    cabecalho_proxy_basic,
)

SENHA_DIFICIL = 'p@ss:w/rd%20#$ "aspas" \\barra çã'
CONTRATOS = [{'id': 7, 'numero': '00012/2025', 'vigencia_fim': '2026-12-31',
              'fornecedor': {'nome': 'EMPRESA TESTE LTDA'}}]

CONFIG = dict(
    CONTRATOSGOV_API_URL='http://api.exemplo.invalid/api',
    CONTRATOSGOV_UG='120006',
    CONTRATOSGOV_PROXY='',
    CONTRATOSGOV_PROXY_USUARIO='',
    CONTRATOSGOV_PROXY_SENHA='',
    CONTRATOSGOV_PROXY_SENHA_ARQUIVO='',
    CONTRATOSGOV_TIMEOUT=5,
)


class ProxyFalso:
    """Proxy HTTP mínimo: registra cada pedido e o Proxy-Authorization decodificado.

    - CONNECT (HTTPS): responde 407 se a credencial não bater, senão 403 (não abre túnel).
    - GET absoluto (HTTP): responde 407 se a credencial não bater, senão o JSON configurado.
    """

    def __init__(self, usuario=None, senha=None, status_get=200, corpo=None):
        self.esperado = f'{usuario}:{senha}' if usuario is not None else None
        self.status_get = status_get
        self.corpo = json.dumps(CONTRATOS if corpo is None else corpo).encode()
        self.pedidos = []  # (linha do pedido, credencial decodificada ou None)
        dono = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                linha = self.rfile.readline().decode('latin-1').strip()
                cred = None
                while True:
                    h = self.rfile.readline()
                    if h in (b'\r\n', b'\n', b''):
                        break
                    nome, _, valor = h.decode('latin-1').partition(':')
                    if nome.strip().lower() == 'proxy-authorization':
                        cred = base64.b64decode(valor.strip().split(' ', 1)[1]).decode('utf-8')
                dono.pedidos.append((linha, cred))
                if dono.esperado is not None and cred != dono.esperado:
                    self.wfile.write(b'HTTP/1.1 407 Proxy Authentication Required\r\n'
                                     b'Proxy-Authenticate: Basic realm="x"\r\nContent-Length: 0\r\n\r\n')
                elif linha.startswith('CONNECT'):
                    self.wfile.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
                else:
                    self.wfile.write(f'HTTP/1.1 {dono.status_get} X\r\nContent-Type: application/json\r\n'
                                     f'Content-Length: {len(dono.corpo)}\r\nConnection: close\r\n\r\n'
                                     .encode() + dono.corpo)

        class Servidor(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        self.servidor = Servidor(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.servidor.server_address[1]}'
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def fechar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


@override_settings(**CONFIG)
class ClienteContratosGovProxyTests(SimpleTestCase):
    def setUp(self):
        self.proxies = []
        sleep = mock.patch('contratos.services.contratosgov.time.sleep')
        sleep.start()
        self.addCleanup(sleep.stop)

    def tearDown(self):
        for p in self.proxies:
            p.fechar()

    def proxy(self, **kw):
        p = ProxyFalso(**kw)
        self.proxies.append(p)
        return p

    def test_http_envia_credencial_com_caracteres_especiais(self):
        p = self.proxy(usuario='fulano.silva', senha=SENHA_DIFICIL)
        cliente = ClienteContratosGov(proxy=p.url, usuario='fulano.silva', senha=SENHA_DIFICIL)
        self.assertEqual(cliente.contratos_ativos(), CONTRATOS)
        linha, cred = p.pedidos[0]
        self.assertEqual(linha, 'GET http://api.exemplo.invalid/api/contrato/ug/120006 HTTP/1.1')
        self.assertEqual(cred, f'fulano.silva:{SENHA_DIFICIL}')

    def test_https_envia_credencial_no_connect(self):
        p = self.proxy(usuario='fulano', senha=SENHA_DIFICIL)
        cliente = ClienteContratosGov(base_url='https://api.exemplo.invalid/api', proxy=p.url,
                                      usuario='fulano', senha=SENHA_DIFICIL)
        # O proxy falso aceita a credencial mas não abre túnel (403): o que importa é o CONNECT.
        with self.assertRaises(ContratosGovErro):
            cliente.contratos_ativos()
        linha, cred = p.pedidos[0]
        self.assertEqual(linha, 'CONNECT api.exemplo.invalid:443 HTTP/1.1')
        self.assertEqual(cred, f'fulano:{SENHA_DIFICIL}')

    def test_senha_errada_em_https_vira_erro_de_autenticacao_sem_repetir(self):
        p = self.proxy(usuario='fulano', senha='certa')
        cliente = ClienteContratosGov(base_url='https://api.exemplo.invalid/api', proxy=p.url,
                                      usuario='fulano', senha='errada')
        with self.assertRaises(ProxyAutenticacaoErro) as ctx:
            cliente.contratos_ativos()
        self.assertNotIn('errada', str(ctx.exception))
        self.assertEqual(len(p.pedidos), 1)

    def test_senha_errada_em_http_vira_erro_de_autenticacao(self):
        p = self.proxy(usuario='fulano', senha='certa')
        cliente = ClienteContratosGov(proxy=p.url, usuario='fulano', senha='errada')
        with self.assertRaises(ProxyAutenticacaoErro):
            cliente.contratos_ativos()

    def test_proxy_sem_credencial_nao_envia_cabecalho(self):
        p = self.proxy()
        ClienteContratosGov(proxy=p.url).contratos_ativos()
        self.assertIsNone(p.pedidos[0][1])

    def test_le_configuracao_do_settings(self):
        p = self.proxy(usuario='svc', senha=SENHA_DIFICIL)
        with self.settings(CONTRATOSGOV_PROXY=p.url, CONTRATOSGOV_PROXY_USUARIO='svc',
                           CONTRATOSGOV_PROXY_SENHA=SENHA_DIFICIL):
            self.assertEqual(ClienteContratosGov().contrato(7), CONTRATOS)
        self.assertIn('/contrato/id/7 ', p.pedidos[0][0])

    def test_senha_lida_de_arquivo_sem_quebra_de_linha_final(self):
        p = self.proxy(usuario='svc', senha=SENHA_DIFICIL)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False) as f:
            f.write(SENHA_DIFICIL + '\n')
        self.addCleanup(os.unlink, f.name)
        with self.settings(CONTRATOSGOV_PROXY=p.url, CONTRATOSGOV_PROXY_USUARIO='svc',
                           CONTRATOSGOV_PROXY_SENHA_ARQUIVO=f.name):
            ClienteContratosGov().contratos_ativos()
        self.assertEqual(p.pedidos[0][1], f'svc:{SENHA_DIFICIL}')

    def test_repete_em_erro_temporario_e_desiste(self):
        p = self.proxy(status_get=503)
        cliente = ClienteContratosGov(proxy=p.url)
        with self.assertRaises(RespostaHTTPErro) as ctx:
            cliente.contratos_ativos()
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(len(p.pedidos), ClienteContratosGov.TENTATIVAS)

    def test_404_nao_repete(self):
        p = self.proxy(status_get=404)
        with self.assertRaises(RespostaHTTPErro):
            ClienteContratosGov(proxy=p.url).contratos_ativos()
        self.assertEqual(len(p.pedidos), 1)

    def test_resposta_html_vira_erro_claro(self):
        p = self.proxy()
        p.corpo = b'<html>Manutencao</html>'
        with self.assertRaisesRegex(ContratosGovErro, 'não é JSON'):
            ClienteContratosGov(proxy=p.url).contratos_ativos()


@override_settings(**CONFIG)
class ClienteContratosGovConfiguracaoTests(SimpleTestCase):
    def test_ignora_proxy_das_variaveis_de_ambiente(self):
        proxy_do_ambiente, api = ProxyFalso(), ProxyFalso()
        self.addCleanup(proxy_do_ambiente.fechar)
        self.addCleanup(api.fechar)
        env = {'HTTP_PROXY': proxy_do_ambiente.url, 'http_proxy': proxy_do_ambiente.url,
               'NO_PROXY': '', 'no_proxy': ''}
        with mock.patch.dict(os.environ, env):
            ClienteContratosGov(base_url=f'{api.url}/api', proxy='').contratos_ativos()
        self.assertEqual(proxy_do_ambiente.pedidos, [])
        self.assertEqual(api.pedidos[0][0], 'GET /api/contrato/ug/120006 HTTP/1.1')

    def test_proxy_sem_esquema_recebe_http(self):
        self.assertEqual(ClienteContratosGov(proxy='proxy-brasilia.intraer:8080').proxy,
                         'http://proxy-brasilia.intraer:8080')

    def test_recusa_credencial_dentro_da_url_do_proxy(self):
        with self.assertRaises(ContratosGovErro):
            ClienteContratosGov(proxy='http://user:senha@proxy:8080')

    def test_descricao_nao_expoe_senha(self):
        cliente = ClienteContratosGov(proxy='http://proxy:8080', usuario='u', senha='segredo')
        self.assertNotIn('segredo', cliente.descricao_proxy())
        self.assertNotIn('segredo', repr(cliente))

    def test_cabecalho_basic_utf8(self):
        valor = cabecalho_proxy_basic('u', 'ç:@')
        self.assertEqual(base64.b64decode(valor.split()[1]).decode('utf-8'), 'u:ç:@')


@override_settings(**CONFIG)
class ComandoTestarContratosGovTests(SimpleTestCase):
    def setUp(self):
        self.p = ProxyFalso(usuario='svc', senha=SENHA_DIFICIL)
        self.addCleanup(self.p.fechar)

    def test_sucesso_com_senha_digitada(self):
        out = StringIO()
        with mock.patch('getpass.getpass', return_value=SENHA_DIFICIL):
            call_command('testar_contratosgov', proxy=self.p.url, usuario='svc', stdout=out)
        saida = out.getvalue()
        self.assertIn('1 contrato(s) ativo(s)', saida)
        self.assertIn('00012/2025', saida)
        self.assertNotIn(SENHA_DIFICIL, saida)

    def test_senha_errada_falha_com_mensagem(self):
        with mock.patch('getpass.getpass', return_value='errada'):
            with self.assertRaisesRegex(CommandError, '407'):
                call_command('testar_contratosgov', proxy=self.p.url, usuario='svc', stdout=StringIO())
