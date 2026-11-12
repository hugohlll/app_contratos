"""Testes da cópia do backup para o servidor de arquivos (SMB), da retenção e da senha cifrada.

O servidor SMB é simulado por `FakeSmbClient`, que grava em uma pasta temporária local.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
import zipfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from contratos.forms import ConfiguracaoSistemaForm
from contratos.models import ConfiguracaoSistema, EmailPendente
from contratos.services import cripto, retencao_backup
from contratos.services.execucao_backup import trava_backup
from contratos.services.servidor_arquivos import (
    ErroServidorArquivos, ServidorArquivos, montar_usuario, normalizar_caminho,
)

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
CAMINHO = r'\\srvarquivos\setor$\SISCONT\Backup'
RETENCAO = {
    'backup_local_retencao_banco': 7, 'backup_local_retencao_midia': 1,
    'backup_remoto_retencao_diaria': 30, 'backup_remoto_retencao_mensal': 12,
    'backup_remoto_retencao_midia': 3,
}


# --------------------------------------------------------------- SMB simulado
class FakeSmbClient(types.ModuleType):
    """Imitação mínima do módulo `smbclient`, gravando em `raiz/<servidor>/<share>/...`."""

    def __init__(self, raiz):
        super().__init__('smbclient')
        self.raiz = Path(raiz)
        self.sessoes = []
        self.falhar_conexao = None

    def _local(self, unc):
        partes = [p for p in unc.replace('/', '\\').split('\\') if p]
        return self.raiz.joinpath(*partes)

    def register_session(self, servidor, username=None, password=None, **kw):
        if self.falhar_conexao:
            raise self.falhar_conexao
        self.sessoes.append((servidor, username, password))

    def delete_session(self, servidor, **kw):
        pass

    def makedirs(self, caminho, exist_ok=False, **kw):
        self._local(caminho).mkdir(parents=True, exist_ok=exist_ok)

    def scandir(self, caminho, **kw):
        return os.scandir(self._local(caminho))

    def open_file(self, caminho, mode='r', **kw):
        return open(self._local(caminho), mode)

    def remove(self, caminho, **kw):
        os.remove(self._local(caminho))

    def replace(self, origem, destino, **kw):
        os.replace(self._local(origem), self._local(destino))


class SmbSimuladoMixin:
    def ligar_smb(self):
        self.smb_raiz = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.smb_raiz, ignore_errors=True)
        self.smb = FakeSmbClient(self.smb_raiz)
        patcher = patch.dict(sys.modules, {'smbclient': self.smb})
        patcher.start()
        self.addCleanup(patcher.stop)

    def remoto(self, *partes):
        return self.smb_raiz.joinpath('srvarquivos', 'setor$', 'SISCONT', 'Backup', *partes)


def _dump_ok(cmd, **kwargs):
    Path(cmd[cmd.index('-f') + 1]).write_text('-- dump --')
    return subprocess.CompletedProcess(cmd, 0)


# ------------------------------------------------------------------- unidade
class RetencaoTests(SimpleTestCase):
    def test_mantem_os_mais_recentes(self):
        nomes = [f"db_backup_202611{d:02d}.sql" for d in range(1, 11)]
        apagar = retencao_backup.selecionar_para_apagar(nomes, 'db_backup_', 7)
        self.assertEqual(sorted(apagar), nomes[:3])

    def test_mantem_primeiro_de_cada_mes(self):
        nomes = ['db_backup_20260901.sql', 'db_backup_20260915.sql', 'db_backup_20261002.sql',
                 'db_backup_20261020.sql', 'db_backup_20261110.sql', 'db_backup_20261111.sql']
        apagar = retencao_backup.selecionar_para_apagar(nomes, 'db_backup_', 2, mensais=2)
        # Mantém os 2 mais recentes (novembro) e o 1º de outubro; setembro fica fora dos 2 meses.
        self.assertEqual(sorted(apagar), ['db_backup_20260901.sql', 'db_backup_20260915.sql',
                                          'db_backup_20261020.sql'])

    def test_ignora_arquivos_fora_do_padrao(self):
        nomes = ['db_backup_20261101.sql', 'leia-me.txt', 'db_backup_manual.sql']
        self.assertEqual(retencao_backup.selecionar_para_apagar(nomes, 'db_backup_', 0), ['db_backup_20261101.sql'])


class CriptoTests(SimpleTestCase):
    def test_ida_e_volta(self):
        token = cripto.cifrar('S3nh@ de rede')
        self.assertNotIn('S3nh@', token)
        self.assertEqual(cripto.decifrar(token), 'S3nh@ de rede')

    def test_outra_secret_key_nao_le(self):
        token = cripto.cifrar('segredo')
        with override_settings(SECRET_KEY='outra-chave-qualquer-bem-diferente'):
            with self.assertRaises(cripto.SegredoIlegivel):
                cripto.decifrar(token)


class CaminhoTests(SimpleTestCase):
    def test_formatos_aceitos(self):
        esperado = ('srv', r'\\srv\dados$\SISCONT')
        self.assertEqual(normalizar_caminho(r'\\srv\dados$\SISCONT'), esperado)
        self.assertEqual(normalizar_caminho('//srv/dados$/SISCONT/'), esperado)
        self.assertEqual(normalizar_caminho('smb://srv/dados$/SISCONT'), esperado)

    def test_formatos_invalidos(self):
        for caminho in ('', 'srv/dados', r'\\srv', 'C:\\backup'):
            with self.subTest(caminho=caminho), self.assertRaises(ErroServidorArquivos):
                normalizar_caminho(caminho)

    def test_usuario_com_dominio(self):
        self.assertEqual(montar_usuario('om.intraer', 'fulano'), 'om.intraer\\fulano')
        self.assertEqual(montar_usuario('om.intraer', 'fulano@om.intraer'), 'fulano@om.intraer')
        self.assertEqual(montar_usuario('', 'fulano'), 'fulano')


class ReplicaTests(SmbSimuladoMixin, SimpleTestCase):
    def setUp(self):
        self.ligar_smb()
        self.origem = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.origem, ignore_errors=True)
        (self.origem / 'prestacoes' / '2026').mkdir(parents=True)
        (self.origem / 'a.pdf').write_text('a')
        (self.origem / 'prestacoes' / '2026' / 'b.pdf').write_text('bb')

    def test_envia_so_novos_ou_alterados_e_nunca_apaga(self):
        with ServidorArquivos(CAMINHO, 'om', 'u', 'p') as srv:
            r1 = srv.replicar_pasta(str(self.origem), 'midia')
            self.assertEqual((r1.total, r1.enviados), (2, 2))
            self.assertEqual(self.remoto('midia', 'prestacoes', '2026', 'b.pdf').read_text(), 'bb')

            r2 = srv.replicar_pasta(str(self.origem), 'midia')
            self.assertEqual(r2.enviados, 0)

            time.sleep(0.01)
            (self.origem / 'a.pdf').write_text('alterado')
            (self.origem / 'prestacoes' / '2026' / 'b.pdf').unlink()
            r3 = srv.replicar_pasta(str(self.origem), 'midia')
            self.assertEqual(r3.enviados, 1)
            self.assertEqual(self.remoto('midia', 'a.pdf').read_text(), 'alterado')
            self.assertTrue(self.remoto('midia', 'prestacoes', '2026', 'b.pdf').exists())
        # Nenhum arquivo temporário deixado para trás
        self.assertFalse(list(self.smb_raiz.rglob('*.parcial')))

    def test_erro_de_login_vira_mensagem_clara(self):
        self.smb.falhar_conexao = Exception('Received unexpected status from the server: STATUS_LOGON_FAILURE')
        with self.assertRaisesMessage(ErroServidorArquivos, 'usuário, senha ou domínio recusados'):
            ServidorArquivos(CAMINHO, 'om', 'u', 'p').conectar()


# ------------------------------------------------------------------ comando
@override_settings(EMAIL_BACKEND=LOCMEM)
@patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
class BackupComServidorArquivosTests(SmbSimuladoMixin, TestCase):
    def setUp(self):
        self.ligar_smb()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.backup_dir = self.tmp / 'backups'
        self.media = self.tmp / 'media'
        self.media.mkdir()
        (self.media / 'a.pdf').write_text('pdf')
        override = override_settings(BACKUP_DIR=str(self.backup_dir), MEDIA_ROOT=str(self.media))
        override.enable()
        self.addCleanup(override.disable)

        self.config = ConfiguracaoSistema.get_config()
        self.config.backup_emails_destinatarios = 'adm@fab.mil.br'
        self.config.backup_remoto_ativo = True
        self.config.backup_remoto_caminho = CAMINHO
        self.config.backup_remoto_dominio = 'om.intraer'
        self.config.backup_remoto_usuario = 'fulano'
        self.config.definir_senha_remota('senha')
        self.config.save()

    def _rodar(self):
        out = StringIO()
        call_command('executar_backup', force=True, stdout=out)
        return out.getvalue()

    def _relatorio(self):
        return EmailPendente.objects.order_by('-pk').first()

    def test_envia_dump_replica_e_zip_mensal(self, _):
        self._rodar()
        self.assertEqual(self.smb.sessoes, [('srvarquivos', 'om.intraer\\fulano', 'senha')])
        self.assertEqual(len(list(self.remoto('banco').glob('db_backup_*.sql'))), 1)
        self.assertEqual(self.remoto('midia', 'a.pdf').read_text(), 'pdf')
        self.assertEqual(len(list(self.remoto('midia_mensal').glob('media_backup_*.zip'))), 1)
        item = self._relatorio()
        self.assertIn('Backup OK', item.assunto)
        self.assertIn('SERVIDOR DE ARQUIVOS', item.corpo_texto)
        self.assertIn('1 enviado(s) de 1', item.corpo_texto)

    def test_segunda_execucao_no_mes_nao_gera_outro_zip(self, _):
        self._rodar()
        zips_antes = sorted(p.name for p in self.backup_dir.glob('media_backup_*.zip'))
        (self.media / 'novo.pdf').write_text('novo')
        self._rodar()
        self.assertEqual(sorted(p.name for p in self.backup_dir.glob('media_backup_*.zip')), zips_antes)
        self.assertTrue(self.remoto('midia', 'novo.pdf').exists())
        item = self._relatorio()
        self.assertIn('Backup OK', item.assunto)
        self.assertIn('Zip mensal deste mês já existe', item.corpo_texto)

    def test_zip_vazio_do_mes_nao_conta_como_zip_mensal(self, _):
        self.backup_dir.mkdir()
        hoje = __import__('datetime').date.today()
        vazio = self.backup_dir / f"media_backup_{hoje:%Y%m}01.zip"
        zipfile.ZipFile(vazio, 'w').close()
        self._rodar()
        self.assertFalse(vazio.exists())  # zip vazio apagado pela retenção
        self.assertEqual(len(list(self.backup_dir.glob('media_backup_*.zip'))), 1)

    def test_falha_no_servidor_gera_parcial_e_mantem_local(self, _):
        self.smb.falhar_conexao = TimeoutError('timed out')
        self._rodar()
        item = self._relatorio()
        self.assertIn('Backup PARCIAL', item.assunto)
        self.assertIn('cópia no servidor de arquivos falhou', item.corpo_texto)
        self.assertIn('não respondeu', item.corpo_texto)
        self.assertEqual(len(list(self.backup_dir.glob('db_backup_*.sql'))), 1)

    def test_senha_ilegivel_gera_parcial(self, _):
        with override_settings(SECRET_KEY='secret-key-trocada-depois-do-cadastro'):
            self._rodar()
        item = self._relatorio()
        self.assertIn('Backup PARCIAL', item.assunto)
        self.assertIn('Cadastre a senha novamente', item.corpo_texto)

    def test_retencao_local_e_remota(self, _):
        self.backup_dir.mkdir()
        for d in range(1, 11):
            (self.backup_dir / f"db_backup_202001{d:02d}.sql").write_text('x')
        self.remoto('banco').mkdir(parents=True)
        for d in range(1, 29):
            (self.remoto('banco') / f"db_backup_201901{d:02d}.sql").write_text('x')
            (self.remoto('banco') / f"db_backup_201902{d:02d}.sql").write_text('x')
        self.config.backup_remoto_retencao_diaria = 5
        self.config.backup_remoto_retencao_mensal = 2
        self.config.save()
        self._rodar()
        # Local: 7 dumps (o de hoje + 6 antigos)
        self.assertEqual(len(list(self.backup_dir.glob('db_backup_*.sql'))), 7)
        # Remoto: 5 mais recentes + 1º dia de cada um dos 2 meses mais recentes
        restantes = sorted(p.name for p in self.remoto('banco').glob('*.sql'))
        self.assertEqual(len(restantes), 6)
        self.assertIn('db_backup_20190201.sql', restantes)
        self.assertNotIn('db_backup_20190101.sql', restantes)

    def test_desativado_nao_conecta_e_avisa_no_relatorio(self, _):
        self.config.backup_remoto_ativo = False
        self.config.save()
        self._rodar()
        self.assertEqual(self.smb.sessoes, [])
        item = self._relatorio()
        self.assertIn('Backup OK', item.assunto)
        self.assertIn('Desativado', item.corpo_texto)

    def test_nao_roda_dois_backups_ao_mesmo_tempo(self, _):
        with trava_backup():
            saida = self._rodar()
        self.assertIn('já existe outro backup em andamento', saida)
        self.assertFalse(EmailPendente.objects.exists())


# ------------------------------------------------------- tela Configurações
class ConfiguracoesServidorArquivosTests(SmbSimuladoMixin, TestCase):
    def setUp(self):
        self.ligar_smb()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        override = override_settings(BACKUP_DIR=f"{tmp}/backups")
        override.enable()
        self.addCleanup(override.disable)
        User.objects.create_superuser(username='adm', password='pw')
        self.client.login(username='adm', password='pw')
        self.url = reverse('configuracoes_sistema')

    def _dados(self, **extra):
        dados = {'backup_periodicidade': 'diario', 'backup_emails_destinatarios': '', **RETENCAO,
                 'backup_remoto_ativo': 'on', 'backup_remoto_caminho': CAMINHO,
                 'backup_remoto_dominio': 'om.intraer', 'backup_remoto_usuario': 'fulano',
                 'backup_remoto_senha': 'senha'}
        dados.update(extra)
        return {k: v for k, v in dados.items() if v is not None}

    def test_campos_comecam_vazios_e_desativados(self):
        config = ConfiguracaoSistema.get_config()
        self.assertFalse(config.backup_remoto_ativo)
        self.assertEqual((config.backup_remoto_caminho, config.backup_remoto_usuario), ('', ''))

    def test_ativar_testa_a_conexao_e_guarda_senha_cifrada(self):
        resposta = self.client.post(self.url, self._dados())
        self.assertRedirects(resposta, self.url)
        config = ConfiguracaoSistema.get_config()
        self.assertTrue(config.backup_remoto_ativo)
        self.assertNotIn('senha', config.backup_remoto_senha_cifrada)
        self.assertEqual(config.obter_senha_remota(), 'senha')
        self.assertEqual(len(self.smb.sessoes), 1)
        self.assertFalse(list(self.remoto().glob('.teste_siscont_*')))  # arquivo de teste apagado

    def test_falha_no_teste_nao_salva(self):
        self.smb.falhar_conexao = Exception('STATUS_LOGON_FAILURE')
        resposta = self.client.post(self.url, self._dados())
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'não foram salvas')
        self.assertFalse(ConfiguracaoSistema.get_config().backup_remoto_ativo)

    def test_senha_em_branco_mantem_a_cadastrada(self):
        self.client.post(self.url, self._dados())
        self.client.post(self.url, self._dados(backup_remoto_senha=None,
                                               backup_emails_destinatarios='x@fab.mil.br'))
        config = ConfiguracaoSistema.get_config()
        self.assertEqual(config.obter_senha_remota(), 'senha')
        self.assertEqual(config.backup_emails_destinatarios, 'x@fab.mil.br')
        self.assertEqual(len(self.smb.sessoes), 1)  # nada de acesso mudou: não testa de novo

    def test_ativar_exige_os_dados_de_acesso(self):
        form = ConfiguracaoSistemaForm(data=self._dados(backup_remoto_caminho='', backup_remoto_usuario='',
                                                        backup_remoto_senha=None),
                                       instance=ConfiguracaoSistema.get_config())
        self.assertFalse(form.is_valid())
        for campo in ('backup_remoto_caminho', 'backup_remoto_usuario', 'backup_remoto_senha'):
            self.assertIn(campo, form.errors)

    def test_caminho_invalido(self):
        form = ConfiguracaoSistemaForm(data=self._dados(backup_remoto_caminho='C:\\backup'),
                                       instance=ConfiguracaoSistema.get_config())
        self.assertFalse(form.is_valid())
        self.assertIn('backup_remoto_caminho', form.errors)

    def test_botao_testar_conexao(self):
        self.client.post(self.url, self._dados())
        resposta = self.client.post(self.url, {'testar_conexao': 'true'}, follow=True)
        self.assertContains(resposta, 'Conexão OK')
        self.smb.falhar_conexao = Exception('STATUS_ACCESS_DENIED')
        resposta = self.client.post(self.url, {'testar_conexao': 'true'}, follow=True)
        self.assertContains(resposta, 'acesso negado')

    def test_aviso_quando_nao_ha_destinatarios(self):
        self.assertContains(self.client.get(self.url), 'Nenhum destinatário cadastrado')
        config = ConfiguracaoSistema.get_config()
        config.backup_emails_destinatarios = 'adm@fab.mil.br'
        config.save()
        self.assertNotContains(self.client.get(self.url), 'Nenhum destinatário cadastrado')

    def test_senha_nao_aparece_na_pagina(self):
        self.client.post(self.url, self._dados(backup_remoto_senha='SenhaSecreta123'))
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, 'SenhaSecreta123')
        self.assertContains(resposta, 'Senha cadastrada')
