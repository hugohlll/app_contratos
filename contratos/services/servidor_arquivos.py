"""
Cópia do backup para um servidor de arquivos da rede (compartilhamento SMB/Windows).

A conexão é feita pelo próprio SISCONT (biblioteca smbprotocol), só durante a cópia: não há
nada montado no sistema operacional. Qualquer erro vira exceção `ErroServidorArquivos`, que o
backup registra no relatório por e-mail.

Organização no destino (dentro do caminho configurado):
    banco\\          dumps do banco (db_backup_AAAAMMDD.sql)
    midia\\          réplica dos anexos: só recebe arquivos novos ou alterados, nunca apaga
    midia_mensal\\   zip completo dos anexos, um por mês (media_backup_AAAAMMDD.zip)
"""
import ntpath
import os
import re
import uuid
from dataclasses import dataclass

PASTA_BANCO = 'banco'
PASTA_MIDIA = 'midia'
PASTA_MIDIA_MENSAL = 'midia_mensal'

TIMEOUT_CONEXAO = 20  # segundos


class ErroServidorArquivos(Exception):
    pass


def normalizar_caminho(caminho):
    """
    Aceita `\\\\servidor\\compartilhamento\\pasta`, `//servidor/compartilhamento/pasta` ou
    `smb://servidor/compartilhamento/pasta`. Retorna (servidor, caminho UNC sem barra final).
    """
    texto = (caminho or '').strip()
    texto = re.sub(r'^smb:', '', texto, flags=re.IGNORECASE)
    partes = [p for p in re.split(r'[\\/]+', texto) if p]
    if len(partes) < 2 or not texto.replace('\\', '/').startswith('//'):
        raise ErroServidorArquivos(
            "Caminho inválido. Use o formato \\\\servidor\\compartilhamento\\pasta "
            "ou smb://servidor/compartilhamento/pasta."
        )
    return partes[0], '\\\\' + '\\'.join(partes)


def montar_usuario(dominio, usuario):
    usuario = (usuario or '').strip()
    dominio = (dominio or '').strip()
    if dominio and '\\' not in usuario and '@' not in usuario:
        return f"{dominio}\\{usuario}"
    return usuario


def _descrever(erro):
    """Mensagem curta e compreensível para os erros mais comuns."""
    nome = type(erro).__name__
    texto = str(erro) or nome
    if 'LOGON_FAILURE' in texto or 'LogonFailure' in nome:
        return "usuário, senha ou domínio recusados pelo servidor de arquivos"
    if 'ACCESS_DENIED' in texto or 'AccessDenied' in nome or isinstance(erro, PermissionError):
        return "acesso negado à pasta (o usuário não tem permissão de escrita?)"
    if 'BAD_NETWORK_NAME' in texto or 'BadNetworkName' in nome:
        return "compartilhamento não encontrado no servidor"
    if isinstance(erro, (TimeoutError,)) or 'timed out' in texto.lower():
        return "o servidor não respondeu (tempo esgotado)"
    if 'Connection refused' in texto or isinstance(erro, ConnectionRefusedError):
        return "conexão recusada na porta 445 (o servidor não aceita SMB ou há bloqueio de firewall)"
    if 'Name or service not known' in texto or 'getaddrinfo' in texto or 'nodename' in texto:
        return "nome do servidor não encontrado na rede (DNS)"
    return f"{nome}: {texto}"


@dataclass
class ResultadoReplica:
    total: int = 0
    enviados: int = 0
    bytes_enviados: int = 0


class ServidorArquivos:
    """Uso: `with ServidorArquivos(caminho, dominio, usuario, senha) as srv: ...`"""

    def __init__(self, caminho, dominio, usuario, senha, timeout=TIMEOUT_CONEXAO):
        self.servidor, self.base = normalizar_caminho(caminho)
        self.usuario = montar_usuario(dominio, usuario)
        self.senha = senha
        self.timeout = timeout
        self._smb = None

    # -------------------------------------------------------------- conexão
    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, *exc):
        self.fechar()
        return False

    def conectar(self):
        import smbclient  # import tardio: só quem usa o servidor de arquivos precisa da biblioteca
        self._smb = smbclient
        try:
            smbclient.register_session(
                self.servidor, username=self.usuario, password=self.senha,
                connection_timeout=self.timeout,
            )
        except Exception as e:
            raise ErroServidorArquivos(f"Não foi possível conectar a {self.servidor}: {_descrever(e)}") from e

    def fechar(self):
        if self._smb is None:
            return
        try:
            self._smb.delete_session(self.servidor)
        except Exception:
            pass
        self._smb = None

    # -------------------------------------------------------------- caminhos
    def caminho(self, *partes):
        return ntpath.join(self.base, *partes) if partes else self.base

    def _executar(self, descricao, funcao, *args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except ErroServidorArquivos:
            raise
        except Exception as e:
            raise ErroServidorArquivos(f"{descricao}: {_descrever(e)}") from e

    # ------------------------------------------------------------ operações
    def garantir_pasta(self, *partes):
        destino = self.caminho(*partes)
        self._executar(f"Erro ao criar a pasta {destino}", self._smb.makedirs, destino, exist_ok=True)
        return destino

    def listar(self, *partes):
        """{nome: (é_pasta, tamanho, mtime)} do conteúdo da pasta; {} se ela não existe."""
        pasta = self.caminho(*partes)

        def _listar():
            itens = {}
            try:
                entradas = list(self._smb.scandir(pasta))
            except FileNotFoundError:
                return itens
            for e in entradas:
                st = e.stat()
                itens[e.name] = (e.is_dir(), st.st_size, st.st_mtime)
            return itens

        return self._executar(f"Erro ao listar {pasta}", _listar)

    def enviar_arquivo(self, origem, *partes):
        """Copia um arquivo local. Grava primeiro com nome temporário e depois renomeia,
        para nunca deixar um arquivo pela metade com o nome definitivo."""
        destino = self.caminho(*partes)
        temporario = f"{destino}.{uuid.uuid4().hex[:8]}.parcial"

        def _enviar():
            try:
                with open(origem, 'rb') as src, self._smb.open_file(temporario, mode='wb') as dst:
                    while True:
                        bloco = src.read(4 * 1024 * 1024)
                        if not bloco:
                            break
                        dst.write(bloco)
                self._smb.replace(temporario, destino)
            except Exception:
                try:
                    self._smb.remove(temporario)
                except Exception:
                    pass
                raise

        self._executar(f"Erro ao enviar {os.path.basename(origem)}", _enviar)
        return destino

    def remover(self, *partes):
        alvo = self.caminho(*partes)
        self._executar(f"Erro ao apagar {alvo}", self._smb.remove, alvo)

    def testar(self):
        """Cria a pasta base, grava, lê e apaga um arquivo de teste."""
        self.garantir_pasta()
        teste = self.caminho(f".teste_siscont_{uuid.uuid4().hex[:8]}")

        def _testar():
            with self._smb.open_file(teste, mode='w') as f:
                f.write('teste de escrita do SISCONT')
            with self._smb.open_file(teste, mode='r') as f:
                f.read()
            self._smb.remove(teste)

        self._executar("Erro ao gravar arquivo de teste", _testar)

    def replicar_pasta(self, origem, *partes):
        """
        Envia os arquivos de `origem` (recursivamente) que não existem no destino, têm tamanho
        diferente ou foram alterados depois da última cópia. Nunca apaga nada no destino.
        """
        resultado = ResultadoReplica()
        for raiz, pastas, arquivos in os.walk(origem):
            pastas.sort()
            relativo = os.path.relpath(raiz, origem)
            sub = [] if relativo == '.' else relativo.split(os.sep)
            destino = list(partes) + sub
            existentes = None
            for nome in sorted(arquivos):
                local = os.path.join(raiz, nome)
                resultado.total += 1
                if existentes is None:
                    self.garantir_pasta(*destino)
                    existentes = self.listar(*destino)
                st = os.stat(local)
                remoto = existentes.get(nome)
                if remoto and not remoto[0] and remoto[1] == st.st_size and remoto[2] >= st.st_mtime:
                    continue
                self.enviar_arquivo(local, *destino, nome)
                resultado.enviados += 1
                resultado.bytes_enviados += st.st_size
        return resultado
