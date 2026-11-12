import os
import datetime
import subprocess
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from contratos.models import ConfiguracaoSistema
from contratos.services import relatorio_backup


class Command(BaseCommand):
    help = 'Executa rotina de backup baseada nas configurações no banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Ignora a periodicidade e força a execução do backup agora',
        )
        parser.add_argument(
            '--usuario',
            default='',
            help='Usuário que disparou o backup manualmente (aparece no relatório por e-mail)',
        )

    # ------------------------------------------------------------------ log
    def _log(self, mensagem, estilo=None):
        """Escreve no stdout (log do cron) e guarda a linha para o relatório por e-mail."""
        self._linhas.append(f"{timezone.localtime():%H:%M:%S} {mensagem}")
        self.stdout.write(estilo(mensagem) if estilo else mensagem)

    def handle(self, *args, **options):
        self._linhas = []
        force = options.get('force', False)
        usuario = options.get('usuario') or ''
        resultado = relatorio_backup.ResultadoBackup(
            inicio=timezone.now(),
            origem='manual' if (force and usuario) else ('forçado' if force else 'automático'),
            usuario=usuario,
            diretorio=getattr(settings, 'BACKUP_DIR', '/backups'),
        )
        executou = self._executar(resultado, force)
        if not executou:
            return
        resultado.fim = timezone.now()
        resultado.log = list(self._linhas)
        relatorio_backup.enviar_relatorio(resultado, self._log)

    def _executar(self, resultado, force):
        """Roda o backup preenchendo `resultado`. Retorna False se foi pulado pela periodicidade."""
        self._log("Iniciando rotina de backup...")

        try:
            config = ConfiguracaoSistema.get_config()
        except Exception as e:
            resultado.erro_geral = f"Erro ao acessar as configurações (banco indisponível?): {e}"
            self._log(resultado.erro_geral, self.style.ERROR)
            return True

        resultado.destinatarios = config.destinatarios_backup
        periodicidade = config.backup_periodicidade

        # Validar periodicidade (se é dia de rodar o backup)
        hoje = datetime.date.today()

        if not force:
            # Se for 'diario', sempre roda.
            if periodicidade == 'semanal':
                # domingo = 6 (monday=0)
                if hoje.weekday() != 6:
                    self._log("Backup ignorado: configurado para 'semanal' e hoje não é domingo.",
                              self.style.NOTICE)
                    return False
            elif periodicidade == 'mensal':
                if hoje.day != 1:
                    self._log("Backup ignorado: configurado para 'mensal' e hoje não é dia 1º.",
                              self.style.NOTICE)
                    return False
        else:
            self._log("Execução forçada solicitada. Ignorando periodicidade.", self.style.NOTICE)

        # Verifica se o diretório de destino existe, tenta criar se não.
        backup_dir = Path(resultado.diretorio)
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(backup_dir, 0o777)
        except Exception as e:
            resultado.erro_geral = f"Não foi possível criar/acessar o diretório de backup {backup_dir}: {e}"
            self._log(resultado.erro_geral, self.style.ERROR)
            return True

        data_str = hoje.strftime("%Y%m%d")
        self._backup_banco(resultado, backup_dir / f"db_backup_{data_str}.sql")
        self._backup_media(resultado, backup_dir / f"media_backup_{data_str}.zip")

        self._log("Rotina de backup finalizada.", self.style.SUCCESS)
        return True

    # --------------------------------------------------------------- banco
    def _backup_banco(self, resultado, sql_file_path):
        self._log("Realizando dump do banco de dados...")
        # Usa as configurações atuais do Django para chamar pg_dump
        db_settings = settings.DATABASES['default']
        env = os.environ.copy()
        if db_settings.get('PASSWORD'):
            env['PGPASSWORD'] = db_settings['PASSWORD']

        dump_command = [
            'pg_dump',
            '-h', str(db_settings.get('HOST') or ''),
            '-p', str(db_settings.get('PORT') or '5432'),
            '-U', str(db_settings.get('USER') or ''),
            '-d', str(db_settings.get('NAME') or ''),
            '-F', 'p',  # formato em texto puro (plain text), legível em bloco de notas
            '-f', str(sql_file_path)
        ]

        banco = resultado.banco
        banco.arquivo = sql_file_path.name
        try:
            subprocess.run(dump_command, env=env, check=True, capture_output=True)
            if sql_file_path.exists():
                os.chmod(sql_file_path, 0o666)
                banco.tamanho = sql_file_path.stat().st_size
            banco.ok = True
            self._log(f"Dump do banco salvo em: {sql_file_path}", self.style.SUCCESS)
        except FileNotFoundError:
            banco.erro = "Comando 'pg_dump' não encontrado. Instale postgresql-client no container."
            self._log(banco.erro, self.style.ERROR)
        except subprocess.CalledProcessError as e:
            detalhe = (e.stderr or b'').decode(errors='replace').strip()
            banco.erro = f"Erro ao executar pg_dump: {detalhe}"
            self._log(banco.erro, self.style.ERROR)
        except Exception as e:
            banco.erro = f"Erro inesperado no dump do banco: {e}"
            self._log(banco.erro, self.style.ERROR)

    # --------------------------------------------------------------- mídia
    def _backup_media(self, resultado, zip_file_path):
        self._log("Compactando pasta mediafiles...")
        media_root = settings.MEDIA_ROOT
        midia = resultado.midia
        midia.arquivo = zip_file_path.name

        if not os.path.exists(media_root):
            midia.erro = f"Pasta MEDIA_ROOT ({media_root}) não encontrada. Nenhuma mídia copiada."
            self._log(midia.erro, self.style.WARNING)
            return
        try:
            quantidade = 0
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(media_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, media_root)
                        zipf.write(file_path, arcname)
                        quantidade += 1
            os.chmod(zip_file_path, 0o666)
            midia.tamanho = zip_file_path.stat().st_size
            midia.quantidade = quantidade
            midia.ok = True
            self._log(f"Mediafiles salvos em: {zip_file_path} ({quantidade} arquivo(s))", self.style.SUCCESS)
            if quantidade == 0:
                midia.aviso = "A pasta de mídia está vazia: nenhum arquivo foi copiado."
                self._log(midia.aviso, self.style.WARNING)
        except Exception as e:
            midia.erro = f"Erro ao compactar pasta media: {e}"
            self._log(midia.erro, self.style.ERROR)
