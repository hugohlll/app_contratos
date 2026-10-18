from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from contratos.models import Comissao, Contrato, Agente, PostoGraduacao, Empresa, ControleExecucao
from datetime import date, timedelta
from django.utils import timezone

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
        # O template usa {% url 'reordenar_integrantes' %}, que o Django resolve
        # para o path real. Por isso verificamos o path resolvido, não o nome da URL.
        url_reordenar = reverse('reordenar_integrantes')
        self.assertContains(response, url_reordenar)

    def test_templates_renderizam_elementos_validacao_upload_10mb(self):
        """Verifica se os templates de upload renderizam os contêineres e scripts de validação de 10 MB."""
        from contratos.models import Setor
        setor = Setor.objects.create(nome="Setor Teste", sigla="ST", ordem=1)

        # 1. Tela de upload de contratos
        url_contrato = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        res_contrato = self.client.get(url_contrato)
        self.assertEqual(res_contrato.status_code, 200)
        self.assertContains(res_contrato, 'id="id_arquivo"')
        self.assertContains(res_contrato, 'id="arquivo-size-error"')
        self.assertContains(res_contrato, 'MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024')
        self.assertContains(res_contrato, 'máx. 10MB.')

        # 2. Tela de upload de setores
        url_setor = reverse('upload_prestacao_setor', kwargs={'setor_id': setor.id})
        res_setor = self.client.get(url_setor)
        self.assertEqual(res_setor.status_code, 200)
        self.assertContains(res_setor, 'id="id_arquivo"')
        self.assertContains(res_setor, 'id="arquivo-size-error"')
        self.assertContains(res_setor, 'MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024')
        self.assertContains(res_setor, 'máx. 10MB.')

        # 3. Dashboard de prestação (modal de slides avulsos)
        url_dashboard = reverse('dashboard_prestacao')
        res_dashboard = self.client.get(url_dashboard)
        self.assertEqual(res_dashboard.status_code, 200)
        self.assertContains(res_dashboard, 'id="slideArquivo"')
        self.assertContains(res_dashboard, 'id="slideArquivo-size-error"')
        self.assertContains(res_dashboard, 'MAX_SLIDE_SIZE_BYTES = 10 * 1024 * 1024')

    def test_botao_registro_tempestivo_ocorrencia_rendering(self):
        """Verifica se o botão para registro/edição de ocorrências é renderizado na tela de prestação."""
        from contratos.models import ControleExecucao

        url_contrato = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        url_ocorrencias = reverse('ocorrencias_contrato', kwargs={'contrato_id': self.contrato.id})

        # 1. Estado sem livro (Pendente)
        res_pendente = self.client.get(url_contrato)
        self.assertEqual(res_pendente.status_code, 200)
        self.assertContains(res_pendente, url_ocorrencias)
        self.assertContains(res_pendente, 'Registro / Edição de Ocorrências')
        self.assertContains(res_pendente, 'bi-journal-plus')
        self.assertContains(res_pendente, 'Atestar e Finalizar Livro do Fiscal')

        # 2. Estado Preenchido / Entregue
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        controle = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=mes_anterior.month,
            ano_referencia=mes_anterior.year,
            agente=self.agente,
            status='entregue'
        )
        res_entregue = self.client.get(url_contrato)
        self.assertEqual(res_entregue.status_code, 200)
        self.assertContains(res_entregue, url_ocorrencias)
        self.assertContains(res_entregue, 'Registro / Edição de Ocorrências')
        self.assertContains(res_entregue, 'Editar Livro do Fiscal')

        # 3. Estado Conformidade (OK)
        controle.status = 'ok'
        controle.save()
        res_ok = self.client.get(url_contrato)
        self.assertEqual(res_ok.status_code, 200)
        self.assertContains(res_ok, url_ocorrencias)
        self.assertContains(res_ok, 'Registro / Edição de Ocorrências')

    def test_upload_prestacao_com_livro_rascunho_sem_agente(self):
        """
        Regressão: garante que a tela upload_prestacao não quebre (VariableDoesNotExist)
        quando houver um ControleExecucao em rascunho sem agente definido (ex: criado via ocorrência).
        """
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=mes_anterior.month,
            ano_referencia=mes_anterior.year,
            agente=None,
            status='rascunho'
        )

        url_contrato = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url_contrato)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A definir na finalização')
        self.assertContains(response, 'Rascunho')

    def test_voltar_de_ocorrencias_para_prestacao_com_rascunho(self):
        """
        Testa o fluxo do usuário: registra uma ocorrência (que gera rascunho sem agente)
        e depois clica em 'Voltar à Prestação de Contas', garantindo renderização com sucesso.
        """
        from contratos.services.ocorrencias import OcorrenciasService

        # Simula criação de ocorrência que resolve e cria livro em rascunho
        dt_agora = timezone.now()
        controle = OcorrenciasService.resolver_livro_para_data(self.contrato, dt_agora)
        self.assertIsNone(controle.agente)
        self.assertEqual(controle.status, 'rascunho')

        # Acessa a tela de prestação (destino do botão 'Voltar à Prestação de Contas')
        url_prestacao = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url_prestacao)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Livro do Fiscal')
        self.assertContains(response, 'Registro / Edição de Ocorrências')



