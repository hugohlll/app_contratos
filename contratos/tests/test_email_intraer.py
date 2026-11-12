"""Testes do envio de e-mail pelo SMTP do Intraer: fila, relatório de backup e comandos."""
import shutil
import smtplib
import ssl
import subprocess
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from contratos.email_backend import IntraerSMTPBackend
from contratos.forms import ConfiguracaoSistemaForm
from contratos.models import ConfiguracaoSistema, EmailPendente
from contratos.services import email as servico_email
from contratos.services import relatorio_backup

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
REMETENTE = 'SCIPG - GAP-BR <scipg.gapbr@fab.mil.br>'


@override_settings(EMAIL_BACKEND=LOCMEM, DEFAULT_FROM_EMAIL=REMETENTE)
class FilaEmailTests(TestCase):
    def test_separar_emails_normaliza_e_remove_repetidos(self):
        self.assertEqual(
            ConfiguracaoSistema.separar_emails(' A@fab.mil.br, b@fab.mil.br;\na@fab.mil.br  '),
            ['a@fab.mil.br', 'b@fab.mil.br'],
        )
        self.assertEqual(ConfiguracaoSistema.separar_emails(''), [])

    def test_sem_destinatario_nao_enfileira(self):
        self.assertIsNone(servico_email.enfileirar([], 'Assunto', 'Texto'))
        self.assertFalse(EmailPendente.objects.exists())

    def test_processar_fila_envia_com_cabecalho_e_aviso(self):
        servico_email.enfileirar('x@fab.mil.br, y@fab.mil.br', 'Assunto', 'Corpo', '<p>Corpo</p>')
        self.assertEqual(servico_email.processar_fila(), (1, 0))

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['x@fab.mil.br', 'y@fab.mil.br'])
        self.assertEqual(msg.from_email, REMETENTE)
        self.assertEqual(msg.extra_headers['Auto-Submitted'], 'auto-generated')
        self.assertIn(servico_email.AVISO_AUTOMATICO, msg.body)
        html, tipo = msg.alternatives[0]
        self.assertEqual(tipo, 'text/html')
        self.assertIn('não responda esta mensagem', html)

        item = EmailPendente.objects.get()
        self.assertEqual(item.status, EmailPendente.STATUS_ENVIADO)
        self.assertEqual(item.tentativas, 1)
        self.assertIsNotNone(item.enviado_em)

    def test_nao_envia_antes_da_proxima_tentativa(self):
        item = servico_email.enfileirar(['x@fab.mil.br'], 'A', 'B')
        item.proxima_tentativa = timezone.now() + timedelta(minutes=5)
        item.save()
        self.assertEqual(servico_email.processar_fila(), (0, 0))
        self.assertEqual(len(mail.outbox), 0)

    def test_falhas_reagendam_e_depois_marcam_falhou(self):
        item = servico_email.enfileirar(['x@fab.mil.br'], 'A', 'B')
        esperados = [2, 5, 15, 30, 60]
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=smtplib.SMTPException('fora')):
            for n, minutos in enumerate(esperados, start=1):
                antes = timezone.now()
                self.assertEqual(servico_email.processar_fila(), (0, 1))
                item.refresh_from_db()
                self.assertEqual(item.status, EmailPendente.STATUS_PENDENTE)
                self.assertEqual(item.tentativas, n)
                self.assertIn('fora', item.ultimo_erro)
                atraso = item.proxima_tentativa - antes
                self.assertAlmostEqual(atraso.total_seconds(), minutos * 60, delta=5)
                item.proxima_tentativa = timezone.now()
                item.save()
            servico_email.processar_fila()
        item.refresh_from_db()
        self.assertEqual(item.status, EmailPendente.STATUS_FALHOU)
        self.assertEqual(item.tentativas, 6)

    def test_servidor_inacessivel_conta_tentativa(self):
        servico_email.enfileirar(['x@fab.mil.br'], 'A', 'B')
        with patch('django.core.mail.backends.locmem.EmailBackend.open', side_effect=OSError('timeout')):
            self.assertEqual(servico_email.processar_fila(), (0, 1))
        item = EmailPendente.objects.get()
        self.assertEqual(item.tentativas, 1)
        self.assertIn('timeout', item.ultimo_erro)

    def test_reenviar_devolve_falhados_para_fila(self):
        item = servico_email.enfileirar(['x@fab.mil.br'], 'A', 'B')
        EmailPendente.objects.filter(pk=item.pk).update(status=EmailPendente.STATUS_FALHOU, tentativas=6)
        self.assertEqual(servico_email.reenviar(EmailPendente.objects.all()), 1)
        item.refresh_from_db()
        self.assertEqual((item.status, item.tentativas), (EmailPendente.STATUS_PENDENTE, 0))

    def test_limpar_antigos_apaga_so_enviados_com_mais_de_90_dias(self):
        velho = servico_email.enfileirar(['x@fab.mil.br'], 'velho', 'B')
        recente = servico_email.enfileirar(['x@fab.mil.br'], 'recente', 'B')
        falhou = servico_email.enfileirar(['x@fab.mil.br'], 'falhou', 'B')
        EmailPendente.objects.filter(pk=velho.pk).update(
            status=EmailPendente.STATUS_ENVIADO, enviado_em=timezone.now() - timedelta(days=91))
        EmailPendente.objects.filter(pk=recente.pk).update(
            status=EmailPendente.STATUS_ENVIADO, enviado_em=timezone.now() - timedelta(days=10))
        EmailPendente.objects.filter(pk=falhou.pk).update(status=EmailPendente.STATUS_FALHOU)
        self.assertEqual(servico_email.limpar_antigos(), 1)
        self.assertEqual(set(EmailPendente.objects.values_list('assunto', flat=True)), {'recente', 'falhou'})

    def test_comando_processar_fila(self):
        servico_email.enfileirar(['x@fab.mil.br'], 'A', 'B')
        out = StringIO()
        call_command('processar_fila_email', stdout=out)
        self.assertIn('1 enviado(s)', out.getvalue())
        out = StringIO()
        call_command('processar_fila_email', stdout=out)
        self.assertEqual(out.getvalue(), '')  # silencioso sem trabalho


class BackendIntraerTests(TestCase):
    @override_settings(EMAIL_SSL_VERIFY=False)
    def test_sem_verificacao_de_certificado(self):
        ctx = IntraerSMTPBackend().ssl_context
        self.assertFalse(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)

    @override_settings(EMAIL_SSL_VERIFY=True)
    def test_com_verificacao_de_certificado(self):
        ctx = IntraerSMTPBackend().ssl_context
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)


@override_settings(EMAIL_BACKEND=LOCMEM)
class TestarEmailComandoTests(TestCase):
    def test_modo_fila(self):
        out = StringIO()
        call_command('testar_email', 'x@fab.mil.br', stdout=out)
        self.assertIn('enviado para x@fab.mil.br', out.getvalue())
        self.assertEqual(EmailPendente.objects.get().categoria, 'TESTE')
        self.assertEqual(len(mail.outbox), 1)

    def test_modo_direto_nao_usa_fila(self):
        call_command('testar_email', 'x@fab.mil.br', '--direto', stdout=StringIO())
        self.assertFalse(EmailPendente.objects.exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_modo_direto_mostra_resposta_do_servidor(self):
        erro = smtplib.SMTPAuthenticationError(535, b'5.7.8 authentication failed')
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=erro):
            with self.assertRaisesMessage(CommandError, '535'):
                call_command('testar_email', 'x@fab.mil.br', '--direto', stdout=StringIO())


class FormDestinatariosBackupTests(TestCase):
    def test_normaliza_lista(self):
        form = ConfiguracaoSistemaForm(data={
            'backup_periodicidade': 'diario',
            'backup_emails_destinatarios': 'A@fab.mil.br; b@fab.mil.br',
        }, instance=ConfiguracaoSistema.get_config())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['backup_emails_destinatarios'], 'a@fab.mil.br, b@fab.mil.br')

    def test_rejeita_email_invalido(self):
        form = ConfiguracaoSistemaForm(data={
            'backup_periodicidade': 'diario',
            'backup_emails_destinatarios': 'ok@fab.mil.br, invalido',
        }, instance=ConfiguracaoSistema.get_config())
        self.assertFalse(form.is_valid())
        self.assertIn('invalido', str(form.errors))

    def test_vazio_e_permitido(self):
        form = ConfiguracaoSistemaForm(data={'backup_periodicidade': 'diario',
                                             'backup_emails_destinatarios': ''},
                                       instance=ConfiguracaoSistema.get_config())
        self.assertTrue(form.is_valid())


def _dump_ok(cmd, **kwargs):
    """Simula o pg_dump gravando o arquivo indicado em -f."""
    Path(cmd[cmd.index('-f') + 1]).write_text('-- dump --')
    return subprocess.CompletedProcess(cmd, 0)


@override_settings(EMAIL_BACKEND=LOCMEM)
class RelatorioBackupTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.backup_dir = self.tmp / 'backups'
        self.media = self.tmp / 'media'
        self.media.mkdir()
        (self.media / 'a.pdf').write_text('pdf')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        override = override_settings(BACKUP_DIR=str(self.backup_dir), MEDIA_ROOT=str(self.media))
        override.enable()
        self.addCleanup(override.disable)
        self.config = ConfiguracaoSistema.get_config()
        self.config.backup_periodicidade = 'diario'
        self.config.backup_emails_destinatarios = 'adm@fab.mil.br'
        self.config.save()

    def _rodar(self, **kwargs):
        out = StringIO()
        call_command('executar_backup', stdout=out, **kwargs)
        return out.getvalue()

    @patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
    def test_sucesso_gera_relatorio_ok_na_fila(self, _):
        saida = self._rodar()
        self.assertIn('colocado na fila de e-mails', saida)
        item = EmailPendente.objects.get()
        self.assertEqual(item.categoria, 'BACKUP')
        self.assertTrue(item.assunto.startswith('[SISCONT] Backup OK – '))
        self.assertEqual(item.destinatarios, 'adm@fab.mil.br')
        self.assertIn('automático', item.corpo_texto)
        self.assertIn('db_backup_', item.corpo_texto)
        self.assertIn('1 arquivo(s)', item.corpo_texto)
        self.assertIn('Espaço livre', item.corpo_texto)
        self.assertIn('Rotina de backup finalizada', item.corpo_texto)  # log completo
        self.assertIn('Backup OK', item.corpo_html)
        # Lista de destinatários guardada para quando o banco estiver fora do ar
        self.assertEqual((self.backup_dir / relatorio_backup.ARQUIVO_DESTINATARIOS).read_text(),
                         'adm@fab.mil.br')

    @patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
    def test_midia_vazia_gera_parcial(self, _):
        (self.media / 'a.pdf').unlink()
        self._rodar()
        self.assertIn('Backup PARCIAL', EmailPendente.objects.get().assunto)

    @patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
    def test_midia_inexistente_gera_parcial(self, _):
        shutil.rmtree(self.media)
        self._rodar()
        item = EmailPendente.objects.get()
        self.assertIn('Backup PARCIAL', item.assunto)
        self.assertIn('não encontrada', item.corpo_texto)

    @patch('contratos.management.commands.executar_backup.subprocess.run',
           side_effect=subprocess.CalledProcessError(1, 'pg_dump', stderr=b'connection refused'))
    def test_falha_no_dump_gera_falhou(self, _):
        self._rodar()
        item = EmailPendente.objects.get()
        self.assertIn('Backup FALHOU', item.assunto)
        self.assertIn('connection refused', item.corpo_texto)

    @patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
    def test_sem_destinatarios_nao_envia(self, _):
        self.config.backup_emails_destinatarios = ''
        self.config.save()
        saida = self._rodar()
        self.assertIn('nenhum destinatário configurado', saida)
        self.assertFalse(EmailPendente.objects.exists())

    def test_dia_pulado_pela_periodicidade_nao_envia(self):
        self.config.backup_periodicidade = 'mensal'
        self.config.save()
        with patch('contratos.management.commands.executar_backup.datetime') as dt:
            import datetime as real
            dt.date.today.return_value = real.date(2026, 6, 15)
            self._rodar()
        self.assertFalse(EmailPendente.objects.exists())

    @patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
    def test_manual_pelo_portal_identifica_usuario(self, _):
        User.objects.create_superuser(username='hugo', password='pw')
        self.client.login(username='hugo', password='pw')
        self.client.post(reverse('configuracoes_sistema'), {'force_backup': 'true'})
        self.assertIn('manual (por hugo)', EmailPendente.objects.get().corpo_texto)

    @patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
    def test_fila_indisponivel_envia_direto(self, _):
        with patch('contratos.services.email.enfileirar', side_effect=Exception('banco fora')):
            saida = self._rodar()
        self.assertIn('enviado direto pelo SMTP', saida)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['adm@fab.mil.br'])

    def test_banco_inacessivel_usa_destinatarios_guardados(self):
        self.backup_dir.mkdir(parents=True)
        (self.backup_dir / relatorio_backup.ARQUIVO_DESTINATARIOS).write_text('guardado@fab.mil.br')
        with patch('contratos.management.commands.executar_backup.ConfiguracaoSistema.get_config',
                   side_effect=Exception('could not connect')), \
                patch('contratos.services.email.enfileirar', side_effect=Exception('banco fora')):
            self._rodar()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['guardado@fab.mil.br'])
        self.assertIn('Backup FALHOU', mail.outbox[0].subject)
        self.assertIn('could not connect', mail.outbox[0].body)

    @patch('contratos.management.commands.executar_backup.subprocess.run', side_effect=_dump_ok)
    def test_fila_e_smtp_indisponiveis_registram_no_log(self, _):
        with patch('contratos.services.email.enfileirar', side_effect=Exception('banco fora')), \
                patch('contratos.services.email.enviar_agora', side_effect=OSError('smtp fora')):
            saida = self._rodar()
        self.assertIn('relatório de backup NÃO enviado', saida)
        self.assertIn('smtp fora', saida)
