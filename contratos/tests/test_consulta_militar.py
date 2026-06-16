from django.test import TestCase, Client
from django.urls import reverse
from contratos.models import (
    Contrato, Empresa, Agente, PostoGraduacao,
    Comissao, Funcao, Integrante
)
from datetime import date, timedelta


class ConsultaMilitarComissaoSemContratoTest(TestCase):
    """
    Testa que a consulta pública de militar não gera erro 500
    quando o integrante pertence a uma comissão sem contrato
    (categoria 'OUTRAS').
    """

    def setUp(self):
        self.client = Client()
        self.posto = PostoGraduacao.objects.create(
            sigla="Sgt", descricao="Sargento", senioridade=5
        )
        self.agente = Agente.objects.create(
            nome_completo="João da Silva",
            nome_de_guerra="SILVA",
            posto=self.posto,
            saram="111222"
        )
        self.funcao = Funcao.objects.create(titulo="Membro", sigla="MBR")

        # Comissão SEM contrato (categoria OUTRAS)
        self.comissao_geral = Comissao.objects.create(
            categoria='OUTRAS',
            contrato=None,
            tipo='PLANEJAMENTO',
            descricao_objeto='Comissão de Planejamento Estratégico',
            ativa=True,
            data_inicio=date.today() - timedelta(days=30),
        )

        # Integrante vinculado à comissão sem contrato
        self.integrante = Integrante.objects.create(
            comissao=self.comissao_geral,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date.today() - timedelta(days=30),
            portaria_numero="001/2026",
            portaria_data=date.today() - timedelta(days=30),
        )

        # Também criar um cenário misto: mesmo militar com comissão de contrato
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Teste LTDA", cnpj="11.111.111/0001-11"
        )
        self.contrato = Contrato.objects.create(
            numero="001/2026", tipo="DESPESA", empresa=self.empresa,
            objeto="Manutenção Predial",
            vigencia_inicio=date.today() - timedelta(days=60),
            vigencia_fim=date.today() + timedelta(days=300),
            valor_total=100000
        )
        self.comissao_contrato = Comissao.objects.create(
            categoria='CONTRATO',
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date.today() - timedelta(days=60),
        )
        self.integrante_contrato = Integrante.objects.create(
            comissao=self.comissao_contrato,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date.today() - timedelta(days=60),
            portaria_numero="002/2026",
            portaria_data=date.today() - timedelta(days=60),
        )

    def test_consulta_por_saram_com_comissao_sem_contrato_nao_gera_500(self):
        """Buscar por SARAM de militar em comissão geral não deve gerar erro 500."""
        url = reverse('consulta_militar') + '?q=111222'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_consulta_por_nome_com_comissao_sem_contrato_nao_gera_500(self):
        """Buscar por nome de guerra de militar em comissão geral não deve gerar erro 500."""
        url = reverse('consulta_militar') + '?q=SILVA'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_consulta_exibe_tipo_comissao_em_vez_de_contrato(self):
        """Para comissões sem contrato, deve exibir o tipo da comissão em vez do número do contrato."""
        url = reverse('consulta_militar') + '?q=SILVA'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Deve conter o tipo da comissão geral
        self.assertContains(response, "Planejamento")

    def test_consulta_exibe_descricao_objeto_para_comissao_geral(self):
        """Para comissões sem contrato, deve exibir a descrição/objeto."""
        url = reverse('consulta_militar') + '?q=SILVA'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planejamento Estratégico")

    def test_consulta_cenario_misto_exibe_ambos(self):
        """Militar com comissões mistas (contrato + geral) deve exibir ambas sem erro."""
        url = reverse('consulta_militar') + '?q=SILVA'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Deve conter o número do contrato da comissão contratual
        self.assertContains(response, "001/2026")
        # E o tipo da comissão geral
        self.assertContains(response, "Planejamento")

    def test_exportar_csv_com_comissao_sem_contrato_nao_gera_500(self):
        """A exportação CSV do histórico militar não deve gerar erro 500 para comissões sem contrato."""
        url = reverse('exportar_historico_militar_csv') + '?q=SILVA'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_exportar_csv_conteudo_comissao_sem_contrato(self):
        """O CSV deve conter o tipo da comissão em vez do número do contrato para comissões gerais."""
        url = reverse('exportar_historico_militar_csv') + '?q=SILVA&formato=csv'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8-sig')
        # Deve conter o tipo da comissão geral
        self.assertIn("Planejamento", content)
        # E o número do contrato da comissão contratual
        self.assertIn("001/2026", content)
