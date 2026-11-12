"""
Serviço de e-mail do SISCONT (SMTP do Intraer).

- `enfileirar()` grava a mensagem em EmailPendente; quem envia é `processar_fila()`,
  chamado pelo comando `processar_fila_email` (cron a cada 2 minutos).
- `enviar_agora()` envia direto pelo SMTP, sem passar pela fila. Usado quando o banco
  pode estar indisponível (falha de backup) e pelo `testar_email --direto`.

Toda mensagem leva o cabeçalho `Auto-Submitted: auto-generated` (RFC 3834), que evita
respostas automáticas, e um aviso visível de que é automática.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

logger = logging.getLogger('contratos.email')

AVISO_AUTOMATICO = 'E-mail automático enviado pelo SISCONT – não responda esta mensagem.'
CABECALHOS = {'Auto-Submitted': 'auto-generated'}

# Espera antes de cada nova tentativa, após a 1ª, 2ª, ... falha. Depois da 5ª nova
# tentativa sem sucesso (6 envios no total, ~2 h), o e-mail fica como FALHOU.
INTERVALOS_TENTATIVA = [
    timedelta(minutes=2),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
    timedelta(minutes=60),
]
MAX_TENTATIVAS = len(INTERVALOS_TENTATIVA) + 1
DIAS_RETENCAO = 90


def _com_aviso_texto(texto):
    return f"{texto.rstrip()}\n\n--\n{AVISO_AUTOMATICO}\n"


def _com_aviso_html(html):
    aviso = (
        '<p style="margin-top:24px;padding-top:8px;border-top:1px solid #ddd;'
        f'color:#777;font-size:12px">{escape(AVISO_AUTOMATICO)}</p>'
    )
    if '</body>' in html:
        return html.replace('</body>', f'{aviso}</body>', 1)
    return html + aviso


def montar_mensagem(destinatarios, assunto, texto, html='', connection=None):
    msg = EmailMultiAlternatives(
        subject=assunto,
        body=_com_aviso_texto(texto),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=list(destinatarios),
        headers=dict(CABECALHOS),
        connection=connection,
    )
    if html:
        msg.attach_alternative(_com_aviso_html(html), 'text/html')
    return msg


def enfileirar(destinatarios, assunto, texto, html='', categoria='GERAL'):
    """Grava a mensagem na fila. Retorna o EmailPendente, ou None se não há destinatário."""
    from contratos.models import ConfiguracaoSistema, EmailPendente

    if isinstance(destinatarios, str):
        destinatarios = ConfiguracaoSistema.separar_emails(destinatarios)
    destinatarios = [d for d in destinatarios if d]
    if not destinatarios:
        logger.warning("E-mail '%s' não enfileirado: nenhum destinatário.", assunto)
        return None
    item = EmailPendente.objects.create(
        categoria=categoria,
        destinatarios=', '.join(destinatarios),
        assunto=assunto[:255],
        corpo_texto=texto,
        corpo_html=html or '',
    )
    logger.info("E-mail #%s enfileirado (%s) para %s: %s", item.pk, categoria, item.destinatarios, assunto)
    return item


def enviar_agora(destinatarios, assunto, texto, html=''):
    """Envia direto pelo SMTP, sem fila. Levanta a exceção do SMTP em caso de falha."""
    msg = montar_mensagem(destinatarios, assunto, texto, html)
    msg.send(fail_silently=False)
    logger.info("E-mail enviado direto para %s: %s", ', '.join(destinatarios), assunto)


def _registrar_falha(item, erro, agora):
    item.tentativas += 1
    item.ultimo_erro = f"{type(erro).__name__}: {erro}"[:2000]
    if item.tentativas >= MAX_TENTATIVAS:
        item.status = item.STATUS_FALHOU
        logger.error("E-mail #%s FALHOU após %s tentativas: %s", item.pk, item.tentativas, item.ultimo_erro)
    else:
        item.proxima_tentativa = agora + INTERVALOS_TENTATIVA[item.tentativas - 1]
        logger.warning("E-mail #%s: tentativa %s falhou (%s). Nova tentativa às %s.",
                       item.pk, item.tentativas, item.ultimo_erro,
                       timezone.localtime(item.proxima_tentativa).strftime('%H:%M'))
    item.save(update_fields=['tentativas', 'ultimo_erro', 'status', 'proxima_tentativa'])


def processar_fila(limite=50):
    """
    Envia os e-mails pendentes cuja próxima tentativa já chegou.
    Usa uma única conexão SMTP para o lote. Retorna (enviados, falhas).
    """
    from contratos.models import EmailPendente

    agora = timezone.now()
    with transaction.atomic():
        ids = list(
            EmailPendente.objects.select_for_update(skip_locked=True)
            .filter(status=EmailPendente.STATUS_PENDENTE, proxima_tentativa__lte=agora)
            .order_by('proxima_tentativa', 'pk')
            .values_list('pk', flat=True)[:limite]
        )
        if not ids:
            return 0, 0
        # Reserva o lote empurrando a próxima tentativa, para que uma execução simultânea
        # do cron não envie as mesmas mensagens.
        EmailPendente.objects.filter(pk__in=ids).update(proxima_tentativa=agora + timedelta(minutes=10))

    enviados = falhas = 0
    connection = get_connection()
    try:
        connection.open()
    except Exception as erro:  # servidor fora do ar: conta uma tentativa para cada item
        for item in EmailPendente.objects.filter(pk__in=ids):
            _registrar_falha(item, erro, agora)
        return 0, len(ids)

    try:
        for item in EmailPendente.objects.filter(pk__in=ids).order_by('pk'):
            try:
                montar_mensagem(item.lista_destinatarios, item.assunto, item.corpo_texto,
                                item.corpo_html, connection=connection).send(fail_silently=False)
            except Exception as erro:
                falhas += 1
                _registrar_falha(item, erro, agora)
                continue
            item.status = item.STATUS_ENVIADO
            item.tentativas += 1
            item.enviado_em = timezone.now()
            item.ultimo_erro = ''
            item.save(update_fields=['status', 'tentativas', 'enviado_em', 'ultimo_erro'])
            enviados += 1
            logger.info("E-mail #%s enviado para %s: %s", item.pk, item.destinatarios, item.assunto)
    finally:
        try:
            connection.close()
        except Exception:
            pass
    return enviados, falhas


def reenviar(queryset):
    """Devolve e-mails que falharam para a fila, zerando as tentativas."""
    from contratos.models import EmailPendente

    return queryset.filter(status=EmailPendente.STATUS_FALHOU).update(
        status=EmailPendente.STATUS_PENDENTE, tentativas=0, proxima_tentativa=timezone.now(), ultimo_erro='',
    )


def limpar_antigos(dias=DIAS_RETENCAO):
    """Apaga e-mails enviados há mais de `dias` dias. Retorna a quantidade apagada."""
    from contratos.models import EmailPendente

    limite = timezone.now() - timedelta(days=dias)
    apagados, _ = EmailPendente.objects.filter(
        status=EmailPendente.STATUS_ENVIADO, enviado_em__lt=limite
    ).delete()
    return apagados
