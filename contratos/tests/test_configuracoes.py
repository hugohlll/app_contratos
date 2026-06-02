import datetime
from unittest.mock import patch, MagicMock
from io import StringIO
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.management import call_command
from contratos.models import ConfiguracaoSistema

class ConfiguracaoSistemaTests(TestCase):
    def setUp(self):
        # Usuário normal
        self.user = User.objects.create_user(username='normal', password='pw')
        # Superusuário
        self.superuser = User.objects.create_superuser(username='super', password='pw')
        
        self.url = reverse('configuracoes_sistema')

    def test_singleton_pattern(self):
        """Garante que apenas uma instância de configuração seja criada"""
        config1 = ConfiguracaoSistema.get_config()
        self.assertEqual(config1.pk, 1)
        
        # Tenta salvar outra instância instanciando e chamando save()
        config2 = ConfiguracaoSistema(
            backup_periodicidade='semanal'
        )
        config2.save()
        # O save sobrescreve o pk para 1, então atualiza a mesma instância
        self.assertEqual(config2.pk, 1)
        self.assertEqual(ConfiguracaoSistema.objects.count(), 1)
        
        # get_config() deve retornar a mesma instância com as novas configurações
        config_atual = ConfiguracaoSistema.get_config()
        self.assertEqual(config_atual.backup_periodicidade, 'semanal')

    def test_acesso_negado_usuario_nao_autenticado(self):
        """Usuários anônimos devem ser redirecionados para o login"""
        response = self.client.get(self.url)
        self.assertRedirects(response, f'/login/?next={self.url}')

    def test_acesso_negado_usuario_normal(self):
        """Usuários não-superusuários devem ser bloqueados e ver erro"""
        self.client.login(username='normal', password='pw')
        response = self.client.get(self.url)
        # Redireciona para painel_controle se for bloqueado no backend da view
        self.assertRedirects(response, reverse('painel_controle'))
        
        # A mensagem de erro deve estar presente
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertIn("apenas superusuários", str(messages[0]).lower())

    def test_acesso_permitido_superusuario(self):
        """Superusuários têm acesso à página de configurações"""
        self.client.login(username='super', password='pw')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contratos/portal/configuracoes.html')

    def test_superusuario_pode_salvar_configuracoes(self):
        """Testa o envio do formulário de configuração"""
        self.client.login(username='super', password='pw')
        data = {
            'backup_periodicidade': 'mensal'
        }
        response = self.client.post(self.url, data)
        
        # Após salvar, redireciona para a mesma página
        self.assertRedirects(response, self.url)
        
        # Verifica se as configurações foram salvas
        config = ConfiguracaoSistema.get_config()
        self.assertEqual(config.backup_periodicidade, 'mensal')

    @patch('django.core.management.call_command')
    def test_superusuario_pode_forcar_backup(self, mock_call_command):
        """Testa a execução forçada do backup via botão"""
        self.client.login(username='super', password='pw')
        data = {
            'force_backup': 'true'
        }
        response = self.client.post(self.url, data)
        
        self.assertRedirects(response, self.url)
        mock_call_command.assert_called_once_with('executar_backup', force=True)


class SidebarConfiguracaoTests(TestCase):
    """Testa a visibilidade do link 'Configurações' na sidebar"""

    def setUp(self):
        self.user = User.objects.create_user(username='normal', password='pw')
        self.superuser = User.objects.create_superuser(username='super', password='pw')
        # Usamos portal_home pois renderiza o base_portal.html com a sidebar
        self.url = reverse('portal_home')

    def test_link_visivel_para_superusuario(self):
        """Superusuário deve ver o link 'Configurações' na sidebar"""
        self.client.login(username='super', password='pw')
        response = self.client.get(self.url)
        self.assertContains(response, 'Configurações')
        self.assertContains(response, reverse('configuracoes_sistema'))

    def test_link_oculto_para_usuario_normal(self):
        """Usuário comum NÃO deve ver o link 'Configurações' na sidebar"""
        self.client.login(username='normal', password='pw')
        response = self.client.get(reverse('listar_empresas'), follow=True)
        self.assertNotContains(response, reverse('configuracoes_sistema'))


class ExecutarBackupPeriodicidadeTests(TestCase):
    """Testa a lógica de periodicidade do comando executar_backup"""

    def setUp(self):
        self.config = ConfiguracaoSistema.get_config()

    @patch('contratos.management.commands.executar_backup.subprocess.run')
    @patch('contratos.management.commands.executar_backup.datetime')
    def test_diario_executa_em_qualquer_dia(self, mock_datetime, mock_subprocess):
        """Periodicidade 'diario' deve executar independentemente do dia"""
        self.config.backup_periodicidade = 'diario'
        self.config.save()

        # Simula uma quarta-feira qualquer
        mock_datetime.date.today.return_value = datetime.date(2026, 6, 3)  # quarta
        mock_datetime.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

        out = StringIO()
        call_command('executar_backup', stdout=out)
        output = out.getvalue()
        self.assertIn('Rotina de backup finalizada', output)
        self.assertNotIn('ignorado', output)

    @patch('contratos.management.commands.executar_backup.subprocess.run')
    @patch('contratos.management.commands.executar_backup.datetime')
    def test_semanal_executa_no_domingo(self, mock_datetime, mock_subprocess):
        """Periodicidade 'semanal' deve executar no domingo"""
        self.config.backup_periodicidade = 'semanal'
        self.config.save()

        # 2026-06-07 é um domingo (weekday() == 6)
        mock_datetime.date.today.return_value = datetime.date(2026, 6, 7)
        mock_datetime.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

        out = StringIO()
        call_command('executar_backup', stdout=out)
        output = out.getvalue()
        self.assertIn('Rotina de backup finalizada', output)
        self.assertNotIn('ignorado', output)

    @patch('contratos.management.commands.executar_backup.datetime')
    def test_semanal_ignora_dias_comuns(self, mock_datetime):
        """Periodicidade 'semanal' NÃO deve executar em dias que não sejam domingo"""
        self.config.backup_periodicidade = 'semanal'
        self.config.save()

        # 2026-06-03 é uma terça-feira (weekday() == 1)
        mock_datetime.date.today.return_value = datetime.date(2026, 6, 3)

        out = StringIO()
        call_command('executar_backup', stdout=out)
        output = out.getvalue()
        self.assertIn('ignorado', output.lower())
        self.assertIn('não é domingo', output)

    @patch('contratos.management.commands.executar_backup.subprocess.run')
    @patch('contratos.management.commands.executar_backup.datetime')
    def test_mensal_executa_no_dia_primeiro(self, mock_datetime, mock_subprocess):
        """Periodicidade 'mensal' deve executar no dia 1º"""
        self.config.backup_periodicidade = 'mensal'
        self.config.save()

        mock_datetime.date.today.return_value = datetime.date(2026, 7, 1)
        mock_datetime.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

        out = StringIO()
        call_command('executar_backup', stdout=out)
        output = out.getvalue()
        self.assertIn('Rotina de backup finalizada', output)
        self.assertNotIn('ignorado', output)

    @patch('contratos.management.commands.executar_backup.datetime')
    def test_mensal_ignora_outros_dias(self, mock_datetime):
        """Periodicidade 'mensal' NÃO deve executar em dias que não sejam o 1º"""
        self.config.backup_periodicidade = 'mensal'
        self.config.save()

        mock_datetime.date.today.return_value = datetime.date(2026, 6, 15)

        out = StringIO()
        call_command('executar_backup', stdout=out)
        output = out.getvalue()
        self.assertIn('ignorado', output.lower())
        self.assertIn('não é dia 1º', output)

    @patch('contratos.management.commands.executar_backup.subprocess.run')
    @patch('contratos.management.commands.executar_backup.datetime')
    def test_force_ignora_periodicidade(self, mock_datetime, mock_subprocess):
        """A flag --force deve ignorar qualquer checagem de dia"""
        self.config.backup_periodicidade = 'mensal'
        self.config.save()

        # Simula um dia que NÃO deveria rodar (15)
        mock_datetime.date.today.return_value = datetime.date(2026, 6, 15)
        mock_datetime.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)

        out = StringIO()
        # Mas passamos force=True
        call_command('executar_backup', force=True, stdout=out)
        output = out.getvalue()
        self.assertIn('Execução forçada solicitada. Ignorando periodicidade.', output)
        self.assertIn('Rotina de backup finalizada', output)
