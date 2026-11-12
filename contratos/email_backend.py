"""
Backend SMTP para o servidor de e-mail do Intraer (mail.intraer:587, STARTTLS).

O certificado apresentado pelo servidor é *.fab.mil.br e não corresponde ao nome
mail.intraer, então a verificação padrão do Django falharia. Com EMAIL_SSL_VERIFY=False
(padrão) a conexão continua criptografada, mas sem verificar o certificado.
"""
import ssl

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property


class IntraerSMTPBackend(EmailBackend):
    @cached_property
    def ssl_context(self):
        if getattr(settings, 'EMAIL_SSL_VERIFY', False):
            return super().ssl_context
        contexto = ssl.create_default_context()
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE
        return contexto
