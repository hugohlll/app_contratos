"""
Teste de envio pelo servidor interno (mail.intraer:587) com dados reais da aplicação:
lista os fiscais (posto/graduação, nome de guerra) de 10 contratos com o número do
contrato e a empresa, em HTML e texto puro.

Deve rodar DENTRO do container de DESENVOLVIMENTO (dados fictícios):
  docker exec -it siscont_dev-web-1 python scripts/tests/teste_smtp_fiscais.py            # só mostra a lista
  docker exec -it siscont_dev-web-1 python scripts/tests/teste_smtp_fiscais.py --enviar   # envia o e-mail

O código de aplicativo é pedido na hora (sem eco) e não é gravado.
O container usa DNS público, por isso o padrão é o IP do mail.intraer (SMTP_HOST muda isso).
"""
import argparse
import getpass
import html
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from contratos.models import Comissao, Integrante  # noqa: E402

HOST = os.getenv("SMTP_HOST", "10.52.202.210")  # mail.intraer
PORT = 587
USUARIO = os.getenv("SMTP_USER", "scipg.gapbr@fab.mil.br")
REMETENTE = USUARIO
DESTINATARIO = "tp.alencarmba@fab.mil.br"
QTD_CONTRATOS = 10


def coletar_linhas():
    comissoes = (
        Comissao.objects.filter(tipo="FISCALIZACAO", ativa=True, contrato__isnull=False)
        .select_related("contrato__empresa")
        .order_by("contrato__numero")
    )
    linhas = []
    contratos_vistos = set()
    for comissao in comissoes:
        if len(contratos_vistos) >= QTD_CONTRATOS:
            break
        fiscais = [
            i for i in Integrante.objects.filter(comissao=comissao, funcao__titulo__istartswith="Fiscal")
            .select_related("agente__posto", "posto_graduacao", "funcao")
            .order_by("funcao__ordem", "ordem")
            if i.is_ativo
        ]
        if not fiscais:
            continue
        contrato = comissao.contrato
        contratos_vistos.add(contrato.pk)
        for i in fiscais:
            posto = i.posto_graduacao or i.agente.posto
            linhas.append({
                "posto": posto.sigla if posto else "",
                "nome_guerra": i.agente.nome_de_guerra,
                "funcao": i.funcao.titulo,
                "contrato": contrato.numero,
                "empresa": contrato.empresa.razao_social,
            })
    return linhas, len(contratos_vistos)


COLUNAS = [("posto", "Posto/Grad."), ("nome_guerra", "Nome de Guerra"), ("funcao", "Função"),
           ("contrato", "Contrato"), ("empresa", "Empresa")]


def montar_texto(linhas):
    larguras = {k: max(len(t), *(len(l[k]) for l in linhas)) for k, t in COLUNAS}
    cab = "  ".join(t.ljust(larguras[k]) for k, t in COLUNAS)
    sep = "  ".join("-" * larguras[k] for k, _ in COLUNAS)
    corpo = ["  ".join(l[k].ljust(larguras[k]) for k, _ in COLUNAS) for l in linhas]
    return "\n".join([cab, sep, *corpo])


def montar_html(linhas, qtd_contratos):
    th = "".join(f'<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #0b5394">{t}</th>'
                 for _, t in COLUNAS)
    trs = []
    for n, l in enumerate(linhas):
        fundo = "#f3f6fa" if n % 2 else "#ffffff"
        tds = "".join(f'<td style="padding:5px 10px;border-bottom:1px solid #dde3ea">{html.escape(l[k])}</td>'
                      for k, _ in COLUNAS)
        trs.append(f'<tr style="background:{fundo}">{tds}</tr>')
    return f"""<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222">
<p>Relação de fiscais de <b>{qtd_contratos} contratos</b> (dados fictícios do ambiente de
desenvolvimento do SISCONT), gerada em {datetime.now():%d/%m/%Y %H:%M}.</p>
<table style="border-collapse:collapse">
<thead><tr>{th}</tr></thead>
<tbody>{''.join(trs)}</tbody>
</table>
<p style="color:#666;font-size:12px">E-mail de teste enviado automaticamente pelo SISCONT
via mail.intraer (porta 587, STARTTLS). Nenhuma ação é necessária.</p>
</body></html>"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--enviar", action="store_true", help="envia o e-mail de verdade")
    args = p.parse_args()

    linhas, qtd = coletar_linhas()
    if not linhas:
        sys.exit("Nenhum fiscal ativo encontrado.")
    texto = montar_texto(linhas)
    print(f"{len(linhas)} fiscais em {qtd} contratos:\n")
    print(texto)

    if not args.enviar:
        print("\nNada enviado (use --enviar).")
        return

    msg = EmailMessage()
    msg["From"] = REMETENTE
    msg["To"] = DESTINATARIO
    msg["Subject"] = f"[Teste SISCONT] Fiscais de {qtd} contratos (dados fictícios)"
    msg.set_content(
        f"Relação de fiscais de {qtd} contratos (dados fictícios do ambiente de desenvolvimento).\n\n"
        f"{texto}\n\nE-mail de teste enviado automaticamente pelo SISCONT. Nenhuma ação é necessária.\n"
    )
    msg.add_alternative(montar_html(linhas, qtd), subtype="html")

    print(f"\nUsuário: {USUARIO}")
    senha = getpass.getpass("Código de aplicativo (não aparece na tela): ")

    # Certificado é *.fab.mil.br e não bate com o nome/IP usado: verificação desligada
    # só neste teste (o canal continua criptografado).
    ctx = ssl._create_unverified_context()
    with smtplib.SMTP(HOST, PORT, timeout=20) as s:
        s.ehlo("siscont-dev")
        s.starttls(context=ctx)
        s.ehlo("siscont-dev")
        try:
            s.login(USUARIO, senha)
        except smtplib.SMTPAuthenticationError as e:
            sys.exit(f"Falha na autenticação: {e.smtp_code} {e.smtp_error.decode(errors='replace')}")
        finally:
            senha = None
        recusados = s.send_message(msg)
    print("Recusados:", recusados or "nenhum")
    print(f"E-mail enviado para {DESTINATARIO}.")


if __name__ == "__main__":
    main()
