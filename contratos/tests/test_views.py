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

    def test_contrato_detail_shows_expired_members(self):
        """Teste se membros com designação encerrada aparecem na tela de detalhes (sem filtro de ativo)"""
        # Criar comissão e integrante expirado
        comissao = Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date.today() - timedelta(days=200),
            data_fim=date.today() - timedelta(days=100) # Expirada
        )
        posto = PostoGraduacao.objects.create(sigla="Sgt", descricao="Sargento", senioridade=5)
        agente = Agente.objects.create(nome_completo="Sargento Antigo", nome_de_guerra="Antigo", saram="12345", posto=posto)
        funcao = Funcao.objects.create(titulo="Membro")
        
        # Integrante expirado
        Integrante.objects.create(
            comissao=comissao,
            agente=agente,
            funcao=funcao,
            data_inicio=date.today() - timedelta(days=200),
            data_fim=date.today() - timedelta(days=100),
            portaria_numero="100", portaria_data=date.today()
        )
        
        url = reverse('detalhe_contrato_portal', kwargs={'pk': self.contrato.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Deve mostrar o nome do integrante mesmo expirado
        self.assertContains(response, "Sgt")
        self.assertContains(response, "Antigo")

class AuditoriaViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='auditor_user', password='password')
        # Add to Auditores group just in case (though view uses @login_required)
        group, _ = Group.objects.get_or_create(name='Auditores')
        self.user.groups.add(group)
        self.user.save()
        self.client.login(username='auditor_user', password='password')
        
        # Setup data for charts
        self.posto = PostoGraduacao.objects.create(sigla="Maj", descricao="Major", senioridade=2)
        self.agente = Agente.objects.create(
            nome_completo="Agente Grafico", 
            nome_de_guerra="Grafico", 
            posto=self.posto, 
            saram="99999",
            cpf="111.111.111-11"
        ) 
        # Wait, Agente doesn't have CNPJ. checking models... Agente has cpf.
        # Fixed in replacement content below.
        
        self.empresa = Empresa.objects.create(razao_social="Empresa G", cnpj="77.777.777/0001-77")
        self.contrato = Contrato.objects.create(
            numero="999/2026", tipo="DESPESA", empresa=self.empresa, objeto="Obj",
            vigencia_inicio=date.today(), vigencia_fim=date.today()+timedelta(days=365),
            valor_total=1000
        )
        # Create Integrante to appear in charts
        self.funcao = Funcao.objects.create(titulo="Gestor", sigla="GES")
        self.comissao = Comissao.objects.create(contrato=self.contrato, tipo="FISCALIZACAO", ativa=True)
        self.integrante = Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao, 
            data_inicio=date.today() - timedelta(days=100),
            portaria_numero="111", portaria_data=date.today()
        )

    def test_chart_labels_contain_rank(self):
        url = reverse('painel_controle')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check context for chart labels
        # p_labels should be in context 'permanencia_labels' (JSON string)
        # We expect "Maj Grafico"
        expected_label = "Maj Grafico"
        self.assertContains(response, expected_label)

    def test_csv_export_contains_rank(self):
        """Testa se a exportação CSV contém o posto/graduação"""
        url = reverse('exportar_radar_permanencia_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # O conteúdo do CSV vem em bytes, decodificamos para verificar texto
        content = response.content.decode('utf-8-sig')
        self.assertIn("Maj Grafico", content)

    def test_agent_list_contains_cpf(self):
        """Teste se a lista de agentes mostra a coluna CPF"""
        url = reverse('listar_agentes')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CPF") # Header
        self.assertContains(response, "111.111.111-11") # Data from setUp

    def test_agent_csv_export_contains_cpf(self):
        """Teste se o CSV de agentes contém o CPF"""
        url = reverse('exportar_agentes_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8-sig')
        self.assertIn("CPF", content)
        self.assertIn("111.111.111-11", content)

    def test_report_period_contains_cpf(self):
        """Teste se o relatório por período mostra coluna CPF"""
        from datetime import date
        url = reverse('relatorio_periodo')
        data_inicio = date.today().strftime('%Y-%m-%d')
        data_fim = date.today().strftime('%Y-%m-%d')
        
        url_query = f"{url}?data_inicial={data_inicio}&data_final={data_fim}"
        response = self.client.get(url_query)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">CPF<")        
        self.assertContains(response, "111.111.111-11")
        self.assertContains(response, "Início")
        self.assertContains(response, "Término (Previsão)")
        self.assertContains(response, "Nº Portaria")
        self.assertContains(response, "Nº Boletim")
        self.assertContains(response, "Tipo Comissão")
        self.assertContains(response, "Fiscalização")
        
        # Ensure no broken template tags are visible
        self.assertNotContains(response, "{{")
        self.assertNotContains(response, "{{")
        self.assertNotContains(response, "}}")
        # should not contain Ativa badge or text
        self.assertNotContains(response, "Ativa")

    def test_report_period_csv_export(self):
        """Teste se a exportação CSV do relatório por período funciona e contém as colunas novas"""
        from datetime import date
        url = reverse('exportar_periodo_csv')
        data_inicio = date.today().strftime('%Y-%m-%d')
        data_fim = date.today().strftime('%Y-%m-%d')
        
        url_query = f"{url}?data_inicial={data_inicio}&data_final={data_fim}"
        response = self.client.get(url_query)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8-sig')
        self.assertIn("CPF", content)
        self.assertIn("Tipo Comissão", content)
        self.assertIn("Fiscalização", content)
        self.assertIn("Tipo Comissão", content)
        self.assertIn("Fiscalização", content)
        self.assertIn("Término (Previsão)", content)
        # Check for presence of at least one date or "Previsto" depending on test data
        # self.assertIn("(Previsto)", content) 

        self.assertNotIn("Ativa", content)
        self.assertIn("111.111.111-11", content)

