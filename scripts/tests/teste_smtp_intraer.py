"""
Teste de envio autenticado pelo servidor de e-mail interno (mail.intraer:587).

A senha nunca fica no código nem no histórico do terminal:
  - por padrão é pedida na hora (getpass, sem eco na tela) e descartada ao final;
  - opcionalmente, é lida de secrets/smtp.env (chmod 600, ignorado pelo git).

Uso:
  python3 scripts/tests/teste_smtp_intraer.py            # só autentica e valida o destinatário (não envia)
  python3 scripts/tests/teste_smtp_intraer.py --enviar   # envia um e-mail de teste de verdade

Formato opcional de secrets/smtp.env:
  SMTP_USER=scipg.gapbr@fab.mil.br
  SMTP_PASSWORD=...
"""
import argparse
import getpass
import os
import smtplib
import ssl
import stat
import sys
from email.message import EmailMessage
from pathlib import Path

HOST = "mail.intraer"
PORT = 587
REMETENTE = "scipg.gapbr@fab.mil.br"
DESTINATARIO = "hugohlll@fab.mil.br"
ARQ_SEGREDOS = Path(__file__).resolve().parents[2] / "secrets" / "smtp.env"


def ler_credenciais():
    if ARQ_SEGREDOS.exists():
        modo = ARQ_SEGREDOS.stat().st_mode
        if modo & (stat.S_IRWXG | stat.S_IRWXO):
            sys.exit(f"{ARQ_SEGREDOS} pode ser lido por outros usuários. Rode: chmod 600 {ARQ_SEGREDOS}")
        dados = {}
        for linha in ARQ_SEGREDOS.read_text().splitlines():
            if "=" in linha and not linha.lstrip().startswith("#"):
                k, v = linha.split("=", 1)
                dados[k.strip()] = v.strip()
        if dados.get("SMTP_USER") and dados.get("SMTP_PASSWORD"):
            print(f"Credenciais lidas de {ARQ_SEGREDOS}")
            return dados["SMTP_USER"], dados["SMTP_PASSWORD"]
    usuario = os.getenv("SMTP_USER", REMETENTE)
    print(f"Usuário: {usuario}")
    senha = getpass.getpass("Senha (não aparece na tela): ")
    return usuario, senha


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--enviar", action="store_true", help="envia o e-mail de teste de verdade")
    args = p.parse_args()

    usuario, senha = ler_credenciais()

    # O certificado do servidor é *.fab.mil.br e não bate com "mail.intraer",
    # então a verificação de nome/AC fica desligada SÓ neste teste. A conexão
    # continua criptografada (a senha não trafega em texto puro).
    ctx = ssl._create_unverified_context()

    with smtplib.SMTP(HOST, PORT, timeout=20) as s:
        s.ehlo("servidoraci.gapbr.intraer")
        s.starttls(context=ctx)
        s.ehlo("servidoraci.gapbr.intraer")
        print(f"STARTTLS ok ({s.sock.version()})")
        try:
            s.login(usuario, senha)
        except smtplib.SMTPAuthenticationError as e:
            sys.exit(f"Falha na autenticação: {e.smtp_code} {e.smtp_error.decode(errors='replace')}")
        finally:
            senha = None
        print("Login ok")

        if not args.enviar:
            print("MAIL FROM:", s.mail(REMETENTE))
            print("RCPT TO:  ", s.rcpt(DESTINATARIO))
            s.rset()
            print("Teste encerrado sem enviar (use --enviar para mandar o e-mail).")
            return

        msg = EmailMessage()
        msg["From"] = REMETENTE
        msg["To"] = DESTINATARIO
        msg["Subject"] = "[Teste SISCONT] Envio automático pela rede interna"
        msg.set_content(
            "Este é um e-mail de teste do SISCONT, enviado automaticamente "
            "pelo servidor mail.intraer (porta 587, STARTTLS).\n\n"
            "Nenhuma ação é necessária."
        )
        recusados = s.send_message(msg)
        print("Recusados:", recusados or "nenhum")
        print("E-mail enviado.")


if __name__ == "__main__":
    main()
