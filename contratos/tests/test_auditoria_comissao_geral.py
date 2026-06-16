from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from contratos.models import (
    Contrato, Empresa, Agente, PostoGraduacao,
    Comissao, Funcao, Integrante
)
from datetime import date, timedelta


class AuditoriaComissaoSemContratoTest(TestCase):
    """
    Testes de regressão para garantir que o painel de auditoria
    e todas as exportações CSV funcionem corretamente quando existem
    comissões ativas da categoria 'OUTRAS' (sem contrato vinculado).
    """

    def setUp(self):
        self.client = Client()
        # Usuário auditor
        self.user = User.objects.create_user(username='auditor', password='pass')
        group, _ = Group.objects.get_or_create(name='Auditores')
        self.user.groups.add(group)
        self.client.login(username='auditor', password='pass')

        self.posto = PostoGraduacao.objects.create(
            sigla="Cap", descricao="Capitão", senioridade=3
        )
        self.agente = Agente.objects.create(
            nome_completo="Carlos Alberto",
            nome_de_guerra="CARLOS",
            posto=self.posto,
            saram="555666",
            cpf="333.333.333-33"
        )
        self.funcao = Funcao.objects.create(titulo="Membro", sigla="MBR")

        # --- Comissão SEM contrato (OUTRAS) ---
        self.comissao_geral = Comissao.objects.create(
            categoria='OUTRAS',
            contrato=None,
            tipo='PLANEJAMENTO',
            descricao_objeto='Planejamento Estratégico 2026',
            ativa=True,
            data_inicio=date.today() - timedelta(days=30),
            data_fim=date.today() + timedelta(days=60),
        )
        self.integrante_geral = Integrante.objects.create(
            comissao=self.comissao_geral,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date.today() - timedelta(days=30),
            data_fim=date.today() + timedelta(days=60),
            portaria_numero="010/2026",
            portaria_data=date.today() - timedelta(days=30),
        )

        # --- Comissão COM contrato (para cenário misto) ---
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Auditoria LTDA", cnpj="22.222.222/0001-22"
        )
        self.contrato = Contrato.objects.create(
            numero="010/2026", tipo="DESPESA", empresa=self.empresa,
            objeto="Manutenção de Ar Condicionado",
            vigencia_inicio=date.today() - timedelta(days=90),
            vigencia_fim=date.today() + timedelta(days=275),
            valor_total=200000
        )
        self.comissao_contrato = Comissao.objects.create(
            categoria='CONTRATO',
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date.today() - timedelta(days=90),
            data_fim=date.today() + timedelta(days=275),
        )
        self.integrante_contrato = Integrante.objects.create(
            comissao=self.comissao_contrato,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date.today() - timedelta(days=90),
            data_fim=date.today() + timedelta(days=275),
            portaria_numero="011/2026",
            portaria_data=date.today() - timedelta(days=90),
        )

    # ========================================
    # Painel de Controle (Dashboard)
    # ========================================

    def test_painel_controle_com_comissao_sem_contrato_nao_gera_500(self):
        """O painel de auditoria não deve quebrar quando há comissões OUTRAS ativas."""
        url = reverse('painel_controle')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ========================================
    # Exportação de Vencimentos CSV
    # ========================================

    def test_exportar_vencimentos_csv_com_comissao_sem_contrato(self):
        """A exportação de vencimentos deve funcionar com comissões sem contrato."""
        url = reverse('exportar_vencimentos_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_exportar_vencimentos_csv_conteudo_sem_contrato(self):
        """O CSV de vencimentos deve conter o tipo da comissão geral em vez do número do contrato."""
        url = reverse('exportar_vencimentos_csv') + '?formato=csv'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8-sig')
        self.assertIn("Planejamento", content)

    # ========================================
    # Exportação Radar de Permanência CSV
    # ========================================

    def test_exportar_radar_permanencia_csv_com_comissao_sem_contrato(self):
        """A exportação do radar de permanência não deve quebrar com comissões gerais."""
        url = reverse('exportar_radar_permanencia_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ========================================
    # Exportação de Qualificação CSV
    # ========================================

    def test_exportar_qualificacao_csv_com_comissao_sem_contrato(self):
        """A exportação de qualificação deve funcionar com comissões sem contrato."""
        url = reverse('exportar_qualificacao_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ========================================
    # Relatório por Período
    # ========================================

    def test_relatorio_periodo_com_comissao_sem_contrato_nao_gera_500(self):
        """O relatório por período deve funcionar quando inclui comissões sem contrato."""
        data_ini = (date.today() - timedelta(days=60)).strftime('%Y-%m-%d')
        data_fim = date.today().strftime('%Y-%m-%d')
        url = reverse('relatorio_periodo') + f'?data_inicial={data_ini}&data_final={data_fim}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Deve conter o tipo da comissão geral
        self.assertContains(response, "Planejamento")

    def test_exportar_periodo_csv_com_comissao_sem_contrato(self):
        """A exportação CSV do relatório por período não deve gerar erro."""
        data_ini = (date.today() - timedelta(days=60)).strftime('%Y-%m-%d')
        data_fim = date.today().strftime('%Y-%m-%d')
        url = reverse('exportar_periodo_csv') + f'?data_inicial={data_ini}&data_final={data_fim}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8-sig')
        self.assertIn("Planejamento", content)

    # ========================================
    # Exportação Geral de Auditoria CSV
    # ========================================

    def test_exportar_auditoria_geral_csv(self):
        """A exportação geral de auditoria não deve falhar."""
        url = reverse('exportar_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ========================================
    # Exportação de Sobrecarga CSV
    # ========================================

    def test_exportar_sobrecarga_fiscais_csv(self):
        """A exportação de sobrecarga deve funcionar normalmente."""
        url = reverse('exportar_sobrecarga_fiscais_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ========================================
    # Exportação de Vencimento de Contratos CSV
    # ========================================

    def test_exportar_contratos_vencimento_csv(self):
        """A exportação de vencimento de contratos deve funcionar normalmente."""
        url = reverse('exportar_contratos_vencimento_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ComissaoGeralSemDataFimTest(TestCase):
    """
    Testa o caso extremo: comissão da categoria OUTRAS que não tem
    nem data_fim nem contrato. O sistema deve ignorá-la graciosamente
    nos cálculos de vencimento sem gerar erros.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='auditor2', password='pass')
        group, _ = Group.objects.get_or_create(name='Auditores')
        self.user.groups.add(group)
        self.client.login(username='auditor2', password='pass')

        self.posto = PostoGraduacao.objects.create(
            sigla="Sgt", descricao="Sargento", senioridade=5
        )
        self.agente = Agente.objects.create(
            nome_completo="Marcos Souza",
            nome_de_guerra="SOUZA",
            posto=self.posto,
            saram="777888",
        )
        self.funcao = Funcao.objects.create(titulo="Presidente", sigla="PRE")

        # Comissão OUTRAS sem data_fim e sem contrato
        self.comissao = Comissao.objects.create(
            categoria='OUTRAS',
            contrato=None,
            tipo='AVALIACAO',
            descricao_objeto='Avaliação de Materiais',
            ativa=True,
            data_inicio=date.today() - timedelta(days=15),
            data_fim=None,  # Sem data fim!
        )
        Integrante.objects.create(
            comissao=self.comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date.today() - timedelta(days=15),
            portaria_numero="099/2026",
            portaria_data=date.today() - timedelta(days=15),
        )

    def test_painel_controle_ignora_comissao_sem_data_fim_sem_contrato(self):
        """O painel não deve quebrar com comissão OUTRAS sem data_fim."""
        url = reverse('painel_controle')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_exportar_vencimentos_ignora_comissao_sem_data_fim_sem_contrato(self):
        """CSV de vencimentos deve simplesmente ignorar comissões sem data_fim e sem contrato."""
        url = reverse('exportar_vencimentos_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
