from django.test import TestCase
from contratos.models import Contrato, Empresa, Agente, PostoGraduacao, Comissao, Integrante, Funcao
from datetime import date, timedelta

class ContratoModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="12.345.678/0001-90")
        self.contrato = Contrato.objects.create(
            numero="001/2026",
            tipo="DESPESA",
            empresa=self.empresa,
            objeto="Objeto Teste",
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=10000.00
        )

    def test_contrato_str(self):
        """Testa a representação em string do contrato"""
        # Ajustado para o formato real do modelo: "CT {numero} - {empresa}"
        self.assertEqual(str(self.contrato), "CT 001/2026 - Empresa Teste")

    def test_contrato_tipo(self):
        """Testa se o tipo é salvo corretamente"""
        self.assertEqual(self.contrato.tipo, "DESPESA")
        
    def test_valores_default(self):
         """Testa valores padrão ou constraints se existirem"""
         self.assertTrue(self.contrato.valor_total > 0)

class AgenteModelTest(TestCase):
    def setUp(self):
        self.posto = PostoGraduacao.objects.create(sigla="Cap", descricao="Capitao", senioridade=1)
        self.agente = Agente.objects.create(
            nome_completo="Joao Silva",
            nome_de_guerra="Silva",
            posto=self.posto,
            cpf="111.111.111-11",
            saram="1234567"
        )

    def test_agente_str(self):
        self.assertEqual(str(self.agente), "Cap Silva")

class ComissaoModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razao_social="Empresa X", cnpj="00.000.000/0001-00")
        self.contrato = Contrato.objects.create(
            numero="002/2026",
            empresa=self.empresa,
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=12000.00
        )
        self.comissao_fisc = Comissao.objects.create(
            contrato=self.contrato,
            tipo="FISCALIZACAO",
            ativa=True
        )

    def test_comissao_creation(self):
        self.assertEqual(self.comissao_fisc.tipo, "FISCALIZACAO")
        self.assertTrue(self.comissao_fisc.ativa)

    def test_integrantes_comissao(self):
        posto = PostoGraduacao.objects.create(sigla="Maj", descricao="Major", senioridade=2)
        agente = Agente.objects.create(
            nome_completo="Maria Souza", 
            nome_de_guerra="Souza", 
            posto=posto, 
            saram="7654321"
        )
        funcao = Funcao.objects.create(titulo="Gestor", sigla="GES")
        
        integrante = Integrante.objects.create(
            comissao=self.comissao_fisc,
            agente=agente,
            funcao=funcao,
            data_inicio=date.today(),
            portaria_numero="123/2026",
            portaria_data=date.today()
        )
        
        self.assertIn(integrante, self.comissao_fisc.integrantes.all())
