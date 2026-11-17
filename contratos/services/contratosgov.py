"""Cliente da API pública do Contratos.gov.br (contratos.comprasnet.gov.br/api).

Somente leitura (GET) e só nos endpoints públicos, que não exigem token.

Proxy: este cliente usa o proxy definido em ``CONTRATOSGOV_PROXY`` e ignora de propósito
as variáveis HTTP_PROXY/HTTPS_PROXY do ambiente. Assim o proxy com senha vale só para estas
chamadas e não desvia o healthcheck em localhost nem outros serviços.

Usuário e senha do proxy NÃO entram na URL: viram o cabeçalho ``Proxy-Authorization: Basic``
montado aqui, então qualquer caractere especial na senha (@ : / % # $ espaço acentos) funciona
sem codificação. Em HTTPS o urllib envia esse cabeçalho no CONNECT do túnel, que é onde o
proxy da Intraer (McAfee Web Gateway) pede a autenticação.
"""
import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger('contratos.contratosgov')

USER_AGENT = 'SISCONT-GAP-BR/1.0 (integracao Contratos.gov.br)'


class ContratosGovErro(Exception):
    """Falha ao consultar a API do Contratos.gov.br."""


class ProxyAutenticacaoErro(ContratosGovErro):
    """O proxy recusou a credencial (HTTP 407)."""


class RespostaHTTPErro(ContratosGovErro):
    """A API respondeu com um código de erro HTTP."""

    def __init__(self, status, url, mensagem=''):
        self.status = status
        self.url = url
        super().__init__(f'HTTP {status} em {url}' + (f': {mensagem}' if mensagem else ''))


def _ler_senha(senha, arquivo):
    if arquivo:
        try:
            with open(arquivo, encoding='utf-8') as f:
                # Remove só a quebra de linha final que editores costumam acrescentar.
                return f.read().rstrip('\r\n')
        except OSError as e:
            raise ContratosGovErro(f'Não foi possível ler o arquivo da senha do proxy ({arquivo}): {e}')
    return senha


def cabecalho_proxy_basic(usuario, senha):
    """Valor do cabeçalho Proxy-Authorization (Basic, UTF-8) para usuário e senha crus."""
    token = base64.b64encode(f'{usuario}:{senha}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


class ClienteContratosGov:
    """Consulta a API do Contratos.gov.br, opcionalmente por um proxy com usuário e senha.

    Sem argumentos, lê a configuração do settings (variáveis CONTRATOSGOV_* do .env).
    """

    TENTATIVAS = 3          # total de tentativas por requisição em falhas temporárias
    ESPERA_INICIAL = 2      # segundos; dobra a cada nova tentativa
    STATUS_TEMPORARIOS = {429, 500, 502, 503, 504}

    def __init__(self, base_url=None, proxy=None, usuario=None, senha=None, timeout=None,
                 senha_arquivo=None):
        self.base_url = (base_url or settings.CONTRATOSGOV_API_URL).rstrip('/')
        self.proxy = settings.CONTRATOSGOV_PROXY if proxy is None else proxy
        self.usuario = settings.CONTRATOSGOV_PROXY_USUARIO if usuario is None else usuario
        if senha is None:
            senha = _ler_senha(
                settings.CONTRATOSGOV_PROXY_SENHA,
                settings.CONTRATOSGOV_PROXY_SENHA_ARQUIVO if senha_arquivo is None else senha_arquivo,
            )
        self._senha = senha
        self.timeout = timeout or settings.CONTRATOSGOV_TIMEOUT

        if self.proxy and '://' not in self.proxy:
            self.proxy = f'http://{self.proxy}'
        if self.proxy and urllib.parse.urlsplit(self.proxy).username:
            raise ContratosGovErro(
                'Não coloque usuário/senha em CONTRATOSGOV_PROXY; use CONTRATOSGOV_PROXY_USUARIO '
                'e CONTRATOSGOV_PROXY_SENHA.'
            )

        # ProxyHandler com dicionário explícito: {} = conexão direta, ignorando o ambiente.
        proxies = {'http': self.proxy, 'https': self.proxy} if self.proxy else {}
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))

    def __repr__(self):
        return f'<ClienteContratosGov {self.base_url} via {self.descricao_proxy()}>'

    def descricao_proxy(self):
        """Descrição do proxy para logs e mensagens, sem expor a senha."""
        if not self.proxy:
            return 'conexão direta (sem proxy)'
        if self.usuario:
            return f'{self.proxy} (usuário {self.usuario}, senha ****)'
        return f'{self.proxy} (sem credencial)'

    # ------------------------------------------------------------------ baixo nível
    def _montar_requisicao(self, url):
        req = urllib.request.Request(url, method='GET', headers={
            'Accept': 'application/json',
            'User-Agent': USER_AGENT,
        })
        if self.proxy and self.usuario:
            req.add_header('Proxy-Authorization', cabecalho_proxy_basic(self.usuario, self._senha))
        return req

    def obter(self, caminho, params=None):
        """GET em ``caminho`` (relativo à base da API) e devolve o JSON já decodificado."""
        url = f'{self.base_url}/{caminho.lstrip("/")}'
        if params:
            url += '?' + urllib.parse.urlencode(params)

        espera = self.ESPERA_INICIAL
        for tentativa in range(1, self.TENTATIVAS + 1):
            try:
                return self._obter_uma_vez(url)
            except RespostaHTTPErro as e:
                if e.status not in self.STATUS_TEMPORARIOS or tentativa == self.TENTATIVAS:
                    raise
                motivo = str(e)
            except ProxyAutenticacaoErro:
                raise  # credencial errada não melhora tentando de novo
            except ContratosGovErro as e:
                if tentativa == self.TENTATIVAS:
                    raise
                motivo = str(e)
            logger.warning('Contratos.gov.br: tentativa %s/%s falhou (%s); nova tentativa em %ss',
                           tentativa, self.TENTATIVAS, motivo, espera)
            time.sleep(espera)
            espera *= 2

    def _obter_uma_vez(self, url):
        req = self._montar_requisicao(url)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                corpo = resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 407:
                raise ProxyAutenticacaoErro(
                    f'O proxy recusou a credencial (407) ao acessar {url}. '
                    f'Proxy: {self.descricao_proxy()}.'
                ) from None
            raise RespostaHTTPErro(e.code, url, e.reason) from None
        except urllib.error.URLError as e:
            motivo = str(e.reason)
            # Em HTTPS, o 407 do proxy chega como falha do túnel (CONNECT), não como HTTPError.
            if '407' in motivo:
                raise ProxyAutenticacaoErro(
                    f'O proxy recusou a credencial (407) ao abrir o túnel para {url}. '
                    f'Proxy: {self.descricao_proxy()}.'
                ) from None
            raise ContratosGovErro(f'Falha de conexão com {url} via {self.descricao_proxy()}: {motivo}') from None
        except TimeoutError:
            raise ContratosGovErro(f'Tempo esgotado ({self.timeout}s) ao acessar {url}') from None
        except OSError as e:  # conexão caiu no meio da leitura etc.
            raise ContratosGovErro(f'Falha de conexão com {url}: {type(e).__name__}: {e}') from None

        try:
            return json.loads(corpo)
        except ValueError:
            # O site às vezes devolve página HTML (manutenção/bloqueio) com status 200.
            inicio = corpo[:120].decode('utf-8', errors='replace').strip()
            raise ContratosGovErro(f'Resposta não é JSON em {url}: {inicio!r}') from None

    # ------------------------------------------------------------------ endpoints públicos
    def contratos_ativos(self, ug=None):
        return self.obter(f'contrato/ug/{ug or settings.CONTRATOSGOV_UG}')

    def contratos_inativos(self, ug=None):
        return self.obter(f'contrato/inativo/ug/{ug or settings.CONTRATOSGOV_UG}')

    def contrato(self, id_contrato):
        return self.obter(f'contrato/id/{int(id_contrato)}')

    def contrato_por_numero(self, uasg, numero_ano):
        """``numero_ano`` no formato da API, ex.: '00012023' (número + ano, sem barra)."""
        return self.obter(f'contrato/ugorigem/{uasg}/numeroano/{numero_ano}')

    def _sub(self, id_contrato, recurso):
        return self.obter(f'contrato/{int(id_contrato)}/{recurso}')

    def historico(self, id_contrato):
        return self._sub(id_contrato, 'historico')

    def responsaveis(self, id_contrato):
        return self._sub(id_contrato, 'responsaveis')

    def prepostos(self, id_contrato):
        return self._sub(id_contrato, 'prepostos')

    def garantias(self, id_contrato):
        return self._sub(id_contrato, 'garantias')

    def empenhos(self, id_contrato):
        return self._sub(id_contrato, 'empenhos')

    def faturas(self, id_contrato):
        return self._sub(id_contrato, 'faturas')

    def ocorrencias(self, id_contrato):
        return self._sub(id_contrato, 'ocorrencias')

    def itens(self, id_contrato):
        return self._sub(id_contrato, 'itens')

    def cronograma(self, id_contrato):
        return self._sub(id_contrato, 'cronograma')

    def publicacoes(self, id_contrato):
        return self._sub(id_contrato, 'publicacoes')

    def arquivos(self, id_contrato):
        return self._sub(id_contrato, 'arquivos')
