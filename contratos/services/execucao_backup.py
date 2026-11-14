"""
Controle de execução do backup: trava contra execuções simultâneas e disparo em segundo plano.

O backup pode levar minutos (zip mensal dos anexos, primeira cópia ao servidor de arquivos),
mais do que o tempo-limite de uma requisição web. Por isso o botão "Executar Backup Agora"
dispara o comando em um processo separado e o resultado chega pelo relatório por e-mail.
"""
import fcntl
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

ARQUIVO_TRAVA = '.backup_em_andamento.lock'
LOG_MANUAL = 'backup_manual.log'


class BackupEmAndamento(Exception):
    pass


def _diretorio():
    pasta = Path(getattr(settings, 'BACKUP_DIR', '/backups'))
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


@contextmanager
def trava_backup():
    """Garante um único backup por vez (entre containers que compartilham a pasta de backup)."""
    arquivo = open(_diretorio() / ARQUIVO_TRAVA, 'a')
    try:
        try:
            fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupEmAndamento("Já existe um backup em andamento.")
        try:
            yield
        finally:
            fcntl.flock(arquivo, fcntl.LOCK_UN)
    finally:
        arquivo.close()


def backup_em_andamento():
    try:
        with trava_backup():
            return False
    except BackupEmAndamento:
        return True


def disparar_em_segundo_plano(usuario):
    """Executa `manage.py executar_backup --force` em um processo independente da requisição."""
    log = open(_diretorio() / LOG_MANUAL, 'ab')
    try:
        subprocess.Popen(
            [sys.executable, os.path.join(settings.BASE_DIR, 'manage.py'),
             'executar_backup', '--force', '--usuario', usuario],
            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True, cwd=str(settings.BASE_DIR),
        )
    finally:
        log.close()
