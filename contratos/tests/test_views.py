from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from contratos.models import Contrato, Empresa, Agente, PostoGraduacao, Comissao, Funcao, Integrante
from datetime import date, timedelta

class PublicViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(razao_social="Empresa Y", cnpj="99.999.999/0001-99")
        self.contrato = Contrato.objects.create(
            numero="003/2026",
            tipo="RECEITA",
            empresa=self.empresa,
            objeto="Objeto Público",
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=50000.00
        )

    def test_home_page_status(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_contrato_detail_public(self):
        url = reverse('detalhe_contrato', args=[self.contrato.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Objeto Público")
        self.assertContains(response, "Receita") # Verifica se o tipo aparece

from django.contrib.auth.models import User, Group

class PortalViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        
        # Criar grupo Auditores e adicionar usuário
        group, _ = Group.objects.get_or_create(name='Auditores')
        self.user.groups.add(group)
        self.user.save()
        
        self.client.login(username='testuser', password='password')
        
        self.empresa = Empresa.objects.create(razao_social="Empresa P", cnpj="88.888.888/0001-88")
        self.contrato = Contrato.objects.create(
            numero="004/2026",
            tipo="DESPESA",
            empresa=self.empresa,
            objeto="Objeto Portal",
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=75000.00
        )

    def test_portal_home_access(self):
        response = self.client.get('/portal/')
        self.assertEqual(response.status_code, 200)

    def test_contrato_list_portal(self):
        """Teste se a lista aparece e contém a coluna Tipo"""
        url = reverse('listar_contratos')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa P")
        self.assertContains(response, "Despesa") # Tipo deve aparecer na tabela

    def test_contrato_detail_portal(self):
         url = reverse('detalhe_contrato_portal', kwargs={'pk': self.contrato.pk})
         response = self.client.get(url)
         self.assertEqual(response.status_code, 200)
         self.assertContains(response, "Objeto Portal")
         self.assertContains(response, "Tipo:") 
         self.assertContains(response, "Despesa")
