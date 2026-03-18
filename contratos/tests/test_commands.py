from django.test import TestCase
from django.core.management import call_command
from datetime import date, timedelta
from contratos.models import Contrato, Empresa, Comissao, Integrante, Agente, PostoGraduacao, Funcao
from io import StringIO

class TestComissaoManagementCommands(TestCase):
    def setUp(self):
        # Set up basic related data required to create a Comissao and Integrantes
        self.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="11.222.333/0001-44")
        self.contrato = Contrato.objects.create(
            numero="12345/2026",
            empresa=self.empresa,
            vigencia_inicio=date(2025, 1, 1),
            vigencia_fim=date(2027, 12, 31),
            valor_total=1000.00
            # tipo defaults to 'DESPESA'
        )

        self.posto = PostoGraduacao.objects.create(sigla="CEL", descricao="Coronel", senioridade=1)
        self.agente = Agente.objects.create(
            nome_completo="João da Silva",
            nome_de_guerra="Silva",
            posto=self.posto,
            saram="1234567"
        )
        self.funcao = Funcao.objects.create(titulo="Presidente", ativa=True, ordem=1)
        
        self.hoje = date.today()

    def test_desativar_comissoes_expiradas(self):
        # Create an active commission that has expired (data_fim < hoje)
        comissao = Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=self.hoje - timedelta(days=30),
            data_fim=self.hoje - timedelta(days=1)
        )
        
        # Add an active member to this commission
        # By default member's data_fim will be same as comissao.data_fim upon creation if null,
        # but let's simulate the bug state where member has a date far in the future
        integrante = Integrante.objects.create(
            comissao=comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=comissao.data_inicio,
            data_fim=self.hoje + timedelta(days=60), # In the future
            portaria_numero="123",
            portaria_data=comissao.data_inicio
        )

        # Ensure the pre-conditions are correct
        self.assertTrue(comissao.ativa)
        self.assertGreater(integrante.data_fim, comissao.data_fim)

        # Capture output
        out = StringIO()
        call_command('desativar_comissoes_expiradas', stdout=out)

        # Refresh
        comissao.refresh_from_db()
        integrante.refresh_from_db()

        # Check conditions after running command
        self.assertFalse(comissao.ativa, "A comissão deveria ter sido desativada.")
        self.assertEqual(comissao.data_fim, self.hoje - timedelta(days=1), "A data de fim da comissão deve ser preservada.")
        self.assertEqual(integrante.data_fim, comissao.data_fim, "A data de fim do integrante deve ser truncada para a data da comissão.")
        self.assertIn("Processo concluído. 1 comissões foram desativadas.", out.getvalue())

    def test_ativar_comissoes_iniciadas(self):
        # Create an inactive commission whose start date is today and has NO end date (null)
        comissao_null_end_date = Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=False,
            data_inicio=self.hoje, # Start date is today
            data_fim=None  # No end date
        )

        # Create an inactive commission whose start date is in the past and end date is in the future
        comissao_future_end_date = Comissao.objects.create(
            contrato=self.contrato,
            tipo='RECEBIMENTO',
            ativa=False,
            data_inicio=self.hoje - timedelta(days=5),
            data_fim=self.hoje + timedelta(days=10)
        )
        
        # Create an inactive commission that already expired (should NOT be activated)
        comissao_expired = Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=False,
            data_inicio=self.hoje - timedelta(days=10),
            data_fim=self.hoje - timedelta(days=1)
        )

        out = StringIO()
        call_command('ativar_comissoes_iniciadas', stdout=out)

        comissao_null_end_date.refresh_from_db()
        comissao_future_end_date.refresh_from_db()
        comissao_expired.refresh_from_db()

        self.assertTrue(comissao_null_end_date.ativa, "Comissão com data de fim nula deveria ser ativada.")
        self.assertTrue(comissao_future_end_date.ativa, "Comissão com data de fim no futuro deveria ser ativada.")
        self.assertFalse(comissao_expired.ativa, "Comissão expirada NÃO deveria ser ativada.")
        self.assertIn("Processo concluído. 2 comissão(ões) ativada(s).", out.getvalue())
