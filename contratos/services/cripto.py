"""
Criptografia de segredos guardados no banco (ex.: senha do servidor de arquivos).

A senha precisa ser lida de volta para ser entregue ao servidor de arquivos, então não pode
ser guardada como hash. Ela é cifrada (Fernet: AES + HMAC) com uma chave derivada da
SECRET_KEY, que fica no .env e não vai para o dump do banco. Quem tiver só o dump vê apenas
o texto cifrado.

Se a SECRET_KEY mudar (ou o sistema for restaurado em um servidor com outra SECRET_KEY), o
texto cifrado deixa de ser legível: basta cadastrar a senha novamente nas Configurações.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_CONTEXTO = b'siscont:segredos-configuracao:v1'


class SegredoIlegivel(Exception):
    """O texto cifrado não pôde ser lido com a SECRET_KEY atual."""


def _fernet():
    chave = hashlib.sha256(_CONTEXTO + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar(texto):
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError) as e:
        raise SegredoIlegivel(
            "A senha guardada não pode ser lida (a SECRET_KEY mudou?). "
            "Cadastre a senha novamente em Configurações."
        ) from e
