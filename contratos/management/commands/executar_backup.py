import os
import datetime
import subprocess
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from contratos.models import ConfiguracaoSistema
from contratos.services import relatorio_backup, retencao_backup
from contratos.services.cripto import SegredoIlegivel
from contratos.services.execucao_backup import trava_backup, BackupEmAndamento
from contratos.services.servidor_arquivos import (
    ErroServidorArquivos, PASTA_BANCO, PASTA_MIDIA, PASTA_MIDIA_MENSAL,
)

PREFIXO_BANCO = 'db_backup_'
PREFIXO_MIDIA = 'media_backup_'


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
        try:
            with trava_backup():
                executou = self._executar(resultado, force)
        except BackupEmAndamento:
            self._log("Backup não executado: já existe outro backup em andamento.", self.style.WARNING)
            return
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

        remoto_ativo = config.backup_remoto_ativo
        resultado.remoto.ativo = remoto_ativo

        data_str = hoje.strftime("%Y%m%d")
        sql_path = backup_dir / f"{PREFIXO_BANCO}{data_str}.sql"
        self._backup_banco(resultado, sql_path)

        # Com o servidor de arquivos ativo, os anexos seguem diariamente pela réplica e o zip
        # completo só é gerado uma vez por mês. Sem ele, o zip continua sendo diário.
        zip_mes = self._zip_valido_do_mes(backup_dir, hoje) if remoto_ativo else None
        if zip_mes:
            self._registrar_midia_sem_zip(resultado, zip_mes)
        else:
            zip_mes = backup_dir / f"{PREFIXO_MIDIA}{data_str}.zip"
            self._backup_media(resultado, zip_mes)

        if remoto_ativo:
            self._enviar_servidor_arquivos(resultado, config, sql_path, zip_mes)

        self._retencao_local(resultado, config, backup_dir)

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
    @staticmethod
    def _contar_arquivos(pasta):
        return sum(len(arquivos) for _, _, arquivos in os.walk(pasta))

    @staticmethod
    def _zip_valido_do_mes(backup_dir, hoje):
        """Zip de mídia já gerado neste mês e com conteúdo (ignora zips vazios)."""
        prefixo = f"{PREFIXO_MIDIA}{hoje:%Y%m}"
        for caminho in sorted(backup_dir.glob(f"{prefixo}??.zip"), reverse=True):
            try:
                with zipfile.ZipFile(caminho) as z:
                    if z.namelist():
                        return caminho
            except (zipfile.BadZipFile, OSError):
                continue
        return None

    def _registrar_midia_sem_zip(self, resultado, zip_mes):
        midia = resultado.midia
        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            midia.erro = f"Pasta MEDIA_ROOT ({media_root}) não encontrada. Nenhuma mídia copiada."
            self._log(midia.erro, self.style.WARNING)
            return
        midia.ok = True
        midia.quantidade = self._contar_arquivos(media_root)
        midia.info = (f"Zip mensal deste mês já existe ({zip_mes.name}); "
                      f"os anexos seguem pela réplica no servidor de arquivos.")
        self._log(midia.info)
        if midia.quantidade == 0:
            midia.aviso = "A pasta de mídia está vazia: nenhum arquivo foi copiado."
            self._log(midia.aviso, self.style.WARNING)

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

    # ------------------------------------------------- servidor de arquivos
    def _enviar_servidor_arquivos(self, resultado, config, sql_path, zip_mes):
        remoto = resultado.remoto
        remoto.destino = config.backup_remoto_caminho
        self._log(f"Enviando cópia ao servidor de arquivos ({remoto.destino})...")
        try:
            with config.servidor_arquivos() as srv:
                remoto.destino = srv.base
                if resultado.banco.ok:
                    srv.garantir_pasta(PASTA_BANCO)
                    srv.enviar_arquivo(str(sql_path), PASTA_BANCO, sql_path.name)
                    remoto.banco_enviado = sql_path.name
                    self._log(f"Dump enviado: {PASTA_BANCO}\\{sql_path.name}")

                if os.path.exists(settings.MEDIA_ROOT):
                    replica = srv.replicar_pasta(settings.MEDIA_ROOT, PASTA_MIDIA)
                    remoto.midia_total = replica.total
                    remoto.midia_enviados = replica.enviados
                    remoto.midia_bytes = replica.bytes_enviados
                    self._log(f"Réplica dos anexos: {replica.enviados} arquivo(s) novo(s) ou alterado(s) "
                              f"enviado(s), de {replica.total}.")

                if resultado.midia.ok and not resultado.midia.aviso and zip_mes and zip_mes.exists():
                    srv.garantir_pasta(PASTA_MIDIA_MENSAL)
                    mes = zip_mes.name[len(PREFIXO_MIDIA):len(PREFIXO_MIDIA) + 6]
                    existentes = srv.listar(PASTA_MIDIA_MENSAL)
                    ja_enviado = any(n.startswith(f"{PREFIXO_MIDIA}{mes}") and not d and t > 22
                                     for n, (d, t, _) in existentes.items())
                    if not ja_enviado:
                        srv.enviar_arquivo(str(zip_mes), PASTA_MIDIA_MENSAL, zip_mes.name)
                        remoto.zip_mensal_enviado = zip_mes.name
                        self._log(f"Zip mensal enviado: {PASTA_MIDIA_MENSAL}\\{zip_mes.name}")

                remoto.removidos = self._retencao_remota(srv, config)

            remoto.ok = resultado.banco.ok
            if not resultado.banco.ok:
                remoto.aviso = "O dump do banco falhou, então não havia dump para enviar."
            self._log("Cópia no servidor de arquivos concluída.", self.style.SUCCESS)
        except (ErroServidorArquivos, SegredoIlegivel) as e:
            remoto.erro = str(e)
            self._log(f"ERRO no envio ao servidor de arquivos: {e}", self.style.ERROR)
        except Exception as e:
            remoto.erro = f"Erro inesperado no envio ao servidor de arquivos: {e}"
            self._log(remoto.erro, self.style.ERROR)

    def _retencao_remota(self, srv, config):
        removidos = 0
        banco = srv.listar(PASTA_BANCO)
        apagar = retencao_backup.selecionar_para_apagar(
            [n for n, (d, _, _) in banco.items() if not d], PREFIXO_BANCO,
            config.backup_remoto_retencao_diaria, config.backup_remoto_retencao_mensal)
        zips = srv.listar(PASTA_MIDIA_MENSAL)
        apagar_zips = retencao_backup.selecionar_para_apagar(
            [n for n, (d, _, _) in zips.items() if not d], PREFIXO_MIDIA,
            config.backup_remoto_retencao_midia)
        for nome in apagar:
            srv.remover(PASTA_BANCO, nome)
            removidos += 1
        for nome in apagar_zips:
            srv.remover(PASTA_MIDIA_MENSAL, nome)
            removidos += 1
        if removidos:
            self._log(f"Retenção no servidor de arquivos: {removidos} backup(s) antigo(s) apagado(s).")
        return removidos

    # ------------------------------------------------------- retenção local
    def _retencao_local(self, resultado, config, backup_dir):
        """Só apaga backups antigos de um tipo se o backup novo desse tipo deu certo."""
        try:
            nomes = [p.name for p in backup_dir.iterdir() if p.is_file()]
        except OSError as e:
            self._log(f"Não foi possível aplicar a retenção local: {e}", self.style.WARNING)
            return
        apagar = []
        if resultado.banco.ok:
            apagar += retencao_backup.selecionar_para_apagar(
                nomes, PREFIXO_BANCO, config.backup_local_retencao_banco)
        if resultado.midia.ok and not resultado.midia.aviso:
            apagar += retencao_backup.selecionar_para_apagar(
                [n for n in nomes if n.endswith('.zip') and self._zip_tem_conteudo(backup_dir / n)],
                PREFIXO_MIDIA, config.backup_local_retencao_midia)
            # Zips vazios (gerados quando a mídia não estava acessível) não servem para restaurar.
            apagar += [n for n in nomes if n.startswith(PREFIXO_MIDIA) and n.endswith('.zip')
                       and not self._zip_tem_conteudo(backup_dir / n)]
        for nome in apagar:
            try:
                (backup_dir / nome).unlink()
            except OSError as e:
                self._log(f"Não foi possível apagar {nome}: {e}", self.style.WARNING)
        if apagar:
            resultado.removidos_locais = len(apagar)
            self._log(f"Retenção local: {len(apagar)} backup(s) antigo(s) apagado(s).")

    @staticmethod
    def _zip_tem_conteudo(caminho):
        try:
            with zipfile.ZipFile(caminho) as z:
                return bool(z.namelist())
        except (zipfile.BadZipFile, OSError):
            return False
