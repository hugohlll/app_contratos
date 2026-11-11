"""
Relatório por e-mail de cada execução do backup.

Status:
- OK       – banco e mídia copiados.
- PARCIAL  – banco copiado, mas a mídia falhou, não foi encontrada ou estava vazia.
- FALHOU   – o dump do banco falhou (ou nem foi possível começar).

O relatório vai para a fila de e-mails. Se não for possível gravar na fila (banco fora do
ar), é enviado direto pelo SMTP; se isso também falhar, o erro fica no log do cron.

Como os destinatários ficam no banco, a última lista conhecida é guardada em
`<BACKUP_DIR>/.destinatarios_relatorio` para avisar mesmo quando o banco está inacessível.
"""
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from django.template.loader import render_to_string
from django.utils import timezone

from contratos.services import email as servico_email

logger = logging.getLogger('contratos.email')

ARQUIVO_DESTINATARIOS = '.destinatarios_relatorio'

STATUS_OK = 'OK'
STATUS_PARCIAL = 'PARCIAL'
STATUS_FALHOU = 'FALHOU'


@dataclass
class ParteBackup:
    arquivo: str = ''
    ok: bool = False
    tamanho: Optional[int] = None
    quantidade: Optional[int] = None
    erro: str = ''
    aviso: str = ''


@dataclass
class ResultadoBackup:
    inicio: object
    origem: str = 'automático'
    usuario: str = ''
    diretorio: str = '/backups'
    fim: object = None
    destinatarios: Optional[List[str]] = None  # None = não foi possível ler do banco
    erro_geral: str = ''
    banco: ParteBackup = field(default_factory=ParteBackup)
    midia: ParteBackup = field(default_factory=ParteBackup)
    log: List[str] = field(default_factory=list)

    @property
    def status(self):
        if self.erro_geral or not self.banco.ok:
            return STATUS_FALHOU
        if not self.midia.ok or self.midia.aviso:
            return STATUS_PARCIAL
        return STATUS_OK

    @property
    def duracao_segundos(self):
        if not self.fim:
            return None
        return int((self.fim - self.inicio).total_seconds())


def formatar_tamanho(n):
    if n is None:
        return '-'
    for unidade in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unidade == 'GB':
            return f"{n:.0f} {unidade}" if unidade == 'B' else f"{n:.1f} {unidade}".replace('.', ',')
        n /= 1024


def formatar_duracao(segundos):
    if segundos is None:
        return '-'
    minutos, seg = divmod(segundos, 60)
    return f"{minutos} min {seg:02d} s" if minutos else f"{seg} s"


def situacao_disco(diretorio):
    """Espaço livre no volume e backups guardados (quantidade e tamanho total)."""
    pasta = Path(diretorio)
    info = {'livre': None, 'total': None, 'quantidade': 0, 'tamanho_backups': 0}
    try:
        uso = shutil.disk_usage(pasta)
        info['livre'], info['total'] = uso.free, uso.total
        arquivos = [p for p in pasta.iterdir()
                    if p.is_file() and p.name.startswith(('db_backup_', 'media_backup_'))]
        info['quantidade'] = len(arquivos)
        info['tamanho_backups'] = sum(p.stat().st_size for p in arquivos)
    except Exception as e:
        info['erro'] = str(e)
    return info


def _contexto(resultado):
    disco = situacao_disco(resultado.diretorio)
    origem = resultado.origem
    if resultado.usuario:
        origem = f"{origem} (por {resultado.usuario})"
    return {
        'r': resultado,
        'status': resultado.status,
        'origem': origem,
        'inicio': timezone.localtime(resultado.inicio),
        'fim': timezone.localtime(resultado.fim) if resultado.fim else None,
        'duracao': formatar_duracao(resultado.duracao_segundos),
        'banco_tamanho': formatar_tamanho(resultado.banco.tamanho),
        'midia_tamanho': formatar_tamanho(resultado.midia.tamanho),
        'disco': disco,
        'disco_livre': formatar_tamanho(disco.get('livre')),
        'disco_total': formatar_tamanho(disco.get('total')),
        'disco_backups': formatar_tamanho(disco.get('tamanho_backups')),
        'log': '\n'.join(resultado.log),
    }


def montar_email(resultado):
    """Retorna (assunto, texto, html)."""
    ctx = _contexto(resultado)
    assunto = f"[SISCONT] Backup {resultado.status} – {ctx['inicio']:%d/%m/%Y}"
    texto = render_to_string('contratos/emails/relatorio_backup.txt', ctx)
    html = render_to_string('contratos/emails/relatorio_backup.html', ctx)
    return assunto, texto, html


# ------------------------------------------------------------ destinatários
def _arquivo_destinatarios(diretorio):
    return Path(diretorio) / ARQUIVO_DESTINATARIOS


def _guardar_destinatarios(diretorio, destinatarios):
    try:
        _arquivo_destinatarios(diretorio).write_text('\n'.join(destinatarios))
    except Exception as e:  # não impede o relatório
        logger.warning("Não foi possível guardar a lista de destinatários do backup: %s", e)


def _destinatarios_guardados(diretorio):
    try:
        return [l.strip() for l in _arquivo_destinatarios(diretorio).read_text().splitlines() if l.strip()]
    except Exception:
        return []


# ------------------------------------------------------------------- envio
def enviar_relatorio(resultado, log=None):
    """Envia (via fila ou direto) o relatório. `log(msg)` recebe as mensagens para o stdout."""
    log = log or (lambda msg, *a: logger.info(msg))

    if resultado.destinatarios is None:
        destinatarios = _destinatarios_guardados(resultado.diretorio)
    else:
        destinatarios = resultado.destinatarios
        _guardar_destinatarios(resultado.diretorio, destinatarios)

    if not destinatarios:
        log("Relatório de backup não enviado: nenhum destinatário configurado.")
        logger.warning("Relatório de backup não enviado: nenhum destinatário configurado.")
        return None

    assunto, texto, html = montar_email(resultado)
    try:
        item = servico_email.enfileirar(destinatarios, assunto, texto, html, categoria='BACKUP')
        log(f"Relatório de backup ({resultado.status}) colocado na fila de e-mails (#{item.pk}).")
        return 'fila'
    except Exception as erro_fila:
        log(f"Não foi possível gravar o relatório na fila ({erro_fila}). Enviando direto pelo SMTP...")
    try:
        servico_email.enviar_agora(destinatarios, assunto, texto, html)
        log("Relatório de backup enviado direto pelo SMTP.")
        return 'direto'
    except Exception as erro_smtp:
        msg = f"ERRO: relatório de backup NÃO enviado (fila e SMTP indisponíveis): {erro_smtp}"
        log(msg)
        logger.error(msg)
        return None
