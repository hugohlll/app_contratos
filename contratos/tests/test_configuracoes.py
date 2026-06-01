from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
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
