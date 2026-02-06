from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from contratos.models import Contrato, Empresa, Agente, PostoGraduacao, Comissao, Funcao, Integrante
from datetime import date, timedelta

class ReproductionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='auditor_user', password='password')
        group, _ = Group.objects.get_or_create(name='Auditores')
        self.user.groups.add(group)
        self.user.save()
        self.client.login(username='auditor_user', password='password')
        
        self.empresa = Empresa.objects.create(razao_social="Empresa Repro", cnpj="11.111.111/0001-11")
        self.contrato = Contrato.objects.create(
            numero="999/2099", tipo="DESPESA", empresa=self.empresa, objeto="Obj",
            vigencia_inicio=date.today(), vigencia_fim=date.today()+timedelta(days=365),
            valor_total=1000
        )
        
        self.posto = PostoGraduacao.objects.create(sigla="Cb", descricao="Cabo", senioridade=2)
        self.agente = Agente.objects.create(
            nome_completo="Cabo Inativo", 
            nome_de_guerra="Inativo", 
            posto=self.posto, 
            saram="88888",
            cpf="222.222.222-22"
        )
        self.funcao = Funcao.objects.create(titulo="Membro", sigla="MEM")

        # Create an INACTIVE commission
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, 
            tipo="FISCALIZACAO", 
            ativa=False,  # <--- INACTIVE
            data_inicio=date.today() - timedelta(days=365),
            data_fim=date.today() - timedelta(days=200)
        )
        
        # Add member to inactive commission
        self.integrante = Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao, 
            data_inicio=date.today() - timedelta(days=365),
            data_fim=date.today() - timedelta(days=200),
            portaria_numero="111", portaria_data=date.today()
        )

    def test_inactive_commission_member_visible(self):
        url = reverse('detalhe_contrato', kwargs={'contrato_id': self.contrato.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # This assert is expected to FAIL currently
        self.assertContains(response, "Inativo")
