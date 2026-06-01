from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from contratos.models import Contrato, Setor, PrestacaoContas, PrestacaoContasSetor, Empresa, Agente, PostoGraduacao

class DashboardObservacaoTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(username='admin_test', password='password123', email='admin@test.com')
        
        # Create auditor group and assign user to it
        self.auditor_group, _ = Group.objects.get_or_create(name="Auditores")
        self.user.groups.add(self.auditor_group)

        # Create basic models needed
        self.posto = PostoGraduacao.objects.create(descricao="Major", sigla="Maj", senioridade=1)
        self.agente = Agente.objects.create(
            nome_completo="Silva Alves",
            nome_de_guerra="Silva",
            posto=self.posto,
            saram="1234567"
        )
        
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Teste LTDA",
            cnpj="12.345.678/0001-99"
        )
        
        hoje = date.today()
        self.contrato = Contrato.objects.create(
            numero="001/2026",
            objeto="Objeto de Teste",
            empresa=self.empresa,
            vigencia_inicio=hoje,
            vigencia_fim=hoje,
            valor_total=1000.00
        )
        
        self.setor = Setor.objects.create(
            nome="Setor de Logistica",
            sigla="SLOG"
        )
        
        # Create prestacao with observation
        self.prestacao = PrestacaoContas.objects.create(
            contrato=self.contrato,
            mes_referencia=hoje.month,
            ano_referencia=hoje.year,
            status='entregue',
            observacao='Observacao do Contrato Especial 123',
            agente=self.agente
        )

        self.prestacao_setor = PrestacaoContasSetor.objects.create(
            setor=self.setor,
            mes_referencia=hoje.month,
            ano_referencia=hoje.year,
            status='entregue',
            observacao='Observacao do Setor Especial 456',
            agente=self.agente
        )

    def test_observacoes_visiveis_no_dashboard(self):
        """As observações do contrato e do setor devem ser exibidas no dashboard"""
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)
        
        # O template exibe o truncatechars:20 da observação.
        # "Observacao do Contrato Especial 123" -> truncated becomes: "Observacao do Con..."
        # Let's verify that the truncated text or the full title is in the HTML.
        self.assertContains(response, 'Observacao do Contrato Especial 123')
        self.assertContains(response, 'Observacao do Setor Especial 456')

    def test_ajax_alterar_status_retorna_observacao(self):
        """A requisição AJAX para alterar status deve conter o campo observacao no JSON retornado"""
        self.client.login(username='admin_test', password='password123')
        
        # Test contracts status change
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.pk, 'novo_status': 'ok'})
        response = self.client.post(url, content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['observacao'], 'Observacao do Contrato Especial 123')
        
        # Test sectors status change
        url_setor = reverse('alterar_status_prestacao_setor', kwargs={'pk': self.prestacao_setor.pk, 'novo_status': 'ok'})
        response_setor = self.client.post(url_setor, content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response_setor.status_code, 200)
        data_setor = response_setor.json()
        self.assertTrue(data_setor['success'])
        self.assertEqual(data_setor['observacao'], 'Observacao do Setor Especial 456')
