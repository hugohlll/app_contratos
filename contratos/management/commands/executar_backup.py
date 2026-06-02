import os
import datetime
import subprocess
import zipfile
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from contratos.models import ConfiguracaoSistema

class Command(BaseCommand):
    help = 'Executa rotina de backup baseada nas configurações no banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Ignora a periodicidade e força a execução do backup agora',
        )

    def handle(self, *args, **options):
        self.stdout.write("Iniciando rotina de backup...")
        
        try:
            config = ConfiguracaoSistema.get_config()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao acessar as configurações: {e}"))
            return

        periodicidade = config.backup_periodicidade
        backup_dir_path = '/backups'
        
        # Validar periodicidade (se é dia de rodar o backup)
        hoje = datetime.date.today()
        force = options.get('force', False)
        
        if not force:
            # Se for 'diario', sempre roda.
            if periodicidade == 'semanal':
                # domingo = 6 (monday=0)
                if hoje.weekday() != 6:
                    self.stdout.write(self.style.NOTICE("Backup ignorado: configurado para 'semanal' e hoje não é domingo."))
                    return
            elif periodicidade == 'mensal':
                if hoje.day != 1:
                    self.stdout.write(self.style.NOTICE("Backup ignorado: configurado para 'mensal' e hoje não é dia 1º."))
                    return
        else:
            self.stdout.write(self.style.NOTICE("Execução forçada solicitada. Ignorando periodicidade."))

        # Verifica se o diretório de destino existe, tenta criar se não.
        backup_dir = Path(backup_dir_path)
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Não foi possível criar/acessar o diretório de backup {backup_dir_path}: {e}"))
            return
            
        data_str = hoje.strftime("%Y%m%d")
        
        # 1. Backup do Banco de Dados (Postgres)
        self.stdout.write("Realizando dump do banco de dados...")
        # Usa as configurações atuais do Django para chamar pg_dump
        db_settings = settings.DATABASES['default']
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_host = db_settings['HOST']
        db_port = db_settings.get('PORT', '5432')
        db_pass = db_settings.get('PASSWORD', '')

        sql_file_path = backup_dir / f"db_backup_{data_str}.sql"
        
        env = os.environ.copy()
        if db_pass:
            env['PGPASSWORD'] = db_pass
            
        dump_command = [
            'pg_dump',
            '-h', db_host,
            '-p', str(db_port),
            '-U', db_user,
            '-d', db_name,
            '-F', 'c',  # formato customizado do pg_dump (mais eficiente e permite restore fácil)
            '-f', str(sql_file_path)
        ]
        
        try:
            # Como a imagem python:3.12 (ou similar) base pode não ter pg_dump instalado, 
            # se falhar o backup do DB, tentamos via docker (se rodar fora) ou temos que instalar postgresql-client
            # No docker-compose, a imagem django costuma ter libpq-dev, mas não pg_dump. 
            # Vamos testar a execução. Se não encontrar pg_dump, vamos logar.
            subprocess.run(dump_command, env=env, check=True, capture_output=True)
            self.stdout.write(self.style.SUCCESS(f"Dump do banco salvo em: {sql_file_path}"))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("Comando 'pg_dump' não encontrado. Instale postgresql-client no container."))
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Erro ao executar pg_dump: {e.stderr.decode()}"))

        # 2. Backup da Pasta Media (Arquivos)
        self.stdout.write("Compactando pasta mediafiles...")
        media_root = settings.MEDIA_ROOT
        zip_file_path = backup_dir / f"media_backup_{data_str}.zip"
        
        if os.path.exists(media_root):
            try:
                with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(media_root):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, media_root)
                            zipf.write(file_path, arcname)
                self.stdout.write(self.style.SUCCESS(f"Mediafiles salvos em: {zip_file_path}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao compactar pasta media: {e}"))
        else:
            self.stdout.write(self.style.WARNING("Pasta MEDIA_ROOT não encontrada. Nenhuma mídia copiada."))

        self.stdout.write(self.style.SUCCESS("Rotina de backup finalizada."))
