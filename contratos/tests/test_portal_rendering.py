from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from contratos.models import Comissao, Contrato, Agente, PostoGraduacao, Empresa
from datetime import date, timedelta

class PortalRenderingTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.force_login(self.user)
        
        # Setup basic data
        self.posto = PostoGraduacao.objects.create(sigla="Maj", descricao="Major", senioridade=2)
        self.agente = Agente.objects.create(
            nome_completo="Agente Teste", 
            nome_de_guerra="Teste", 
            posto=self.posto, 
            saram="12345",
            cpf="000.000.000-00"
        )
        self.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="00.000.000/0001-00")
        self.contrato = Contrato.objects.create(
            numero="001/2024", 
            objeto="Teste",
            tipo="DESPESA",
            empresa=self.empresa,
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=1000.00
        )
        self.comissao = Comissao.objects.create(contrato=self.contrato, tipo='FISCALIZACAO', data_inicio=date.today())

    def test_editar_comissao_rendering(self):
        url = reverse('editar_comissao', args=[self.comissao.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Check if reordenar_integrantes URL is in the content
        self.assertContains(response, 'reordenar_integrantes')
