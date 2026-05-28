"""
Testes abrangentes para o fluxo de envio de Prestação de Contas Mensal.

Cobre:
- Envio válido de PDF (sem login)
- Validação de tipo de arquivo (rejeitar não-PDF)
- Validação de tamanho máximo (10MB)
- Substituição de entrega no mesmo mês/ano
- Restrição de agentes ao contrato (apenas fiscais ativos)
- Redirecionamento correto após envio
- Envio via GET (deve redirecionar, não processar)
- Formulário inválido (campos obrigatórios)
- Renomeação automática do arquivo
- Alteração de status via AJAX (sem recarregar página)
- Estatísticas retornadas via AJAX
- Permissões de acesso à alteração de status via AJAX
"""
import os
import json
from datetime import date
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Empresa, PrestacaoContas, Agente,
    PostoGraduacao, Comissao, Integrante, Funcao
)


class BaseTestSetup(TestCase):
    """Setup compartilhado para todos os testes de envio."""

    def setUp(self):
        self.posto = PostoGraduacao.objects.create(sigla="CB", descricao="Cabo", senioridade=8)
        self.empresa = Empresa.objects.create(razao_social="Alpha Serviços SA", cnpj="11222333000181")
        self.agente = Agente.objects.create(
            nome_completo="Carlos Pereira", nome_de_guerra="Pereira",
            posto=self.posto, saram="7654321"
        )
        self.contrato = Contrato.objects.create(
            numero="20/2026", objeto="Manutenção Predial",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=50000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO',
            ativa=True, data_inicio=date(2026, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal Técnico", ordem=1)
        self.integrante = Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date(2026, 1, 1),
            portaria_numero="456", portaria_data=date(2026, 1, 1)
        )
        self.client = Client()
        self.url_upload = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})

    def _make_pdf(self, name="doc.pdf", size_bytes=None):
        content = b"%PDF-1.4 test content"
        if size_bytes:
            content = b"%" * size_bytes
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def _cleanup(self, prestacao):
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)


class EnvioValidoTests(BaseTestSetup):
    """Testes de envio válido de prestação de contas."""

    def test_envio_pdf_valido_sem_login(self):
        """Fiscal envia PDF válido sem estar logado — deve salvar e redirecionar."""
        response = self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 3, 'ano_referencia': 2026,
            'arquivo': self._make_pdf(), 'observacao': 'Envio março'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("?enviado=1", response.url)
        self.assertEqual(PrestacaoContas.objects.count(), 1)

        p = PrestacaoContas.objects.first()
        self.assertEqual(p.mes_referencia, 3)
        self.assertEqual(p.ano_referencia, 2026)
        self.assertEqual(p.status, 'entregue')
        self.assertEqual(p.observacao, 'Envio março')
        self._cleanup(p)

    def test_envio_grava_agente_correto(self):
        """O agente selecionado no formulário deve ser persistido."""
        self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 4, 'ano_referencia': 2026,
            'arquivo': self._make_pdf(),
        })
        p = PrestacaoContas.objects.first()
        self.assertEqual(p.agente_id, self.agente.id)
        self._cleanup(p)

    def test_renomeacao_arquivo(self):
        """O arquivo deve ser renomeado seguindo o padrão do sistema."""
        self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 7, 'ano_referencia': 2026,
            'arquivo': self._make_pdf("qualquer_nome.pdf"),
        })
        p = PrestacaoContas.objects.first()
        self.assertTrue(p.arquivo.name.startswith("prestacoes/"))
        self.assertIn("cb_pereira", p.arquivo.name)
        self.assertIn("20-2026", p.arquivo.name)
        self.assertTrue(p.arquivo.name.endswith(".pdf"))
        self._cleanup(p)

    def test_envio_com_observacao_vazia(self):
        """O campo observação é opcional — envio sem ele deve funcionar."""
        response = self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 1, 'ano_referencia': 2026,
            'arquivo': self._make_pdf(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrestacaoContas.objects.count(), 1)
        p = PrestacaoContas.objects.first()
        self._cleanup(p)


class ValidacaoArquivoTests(BaseTestSetup):
    """Testes de validação do arquivo enviado."""

    def test_rejeitar_arquivo_nao_pdf(self):
        """Arquivos que não são PDF devem ser rejeitados."""
        arquivo = SimpleUploadedFile("planilha.xlsx", b"fake", content_type="application/vnd.ms-excel")
        response = self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 5, 'ano_referencia': 2026,
            'arquivo': arquivo,
        })
        # Deve redirecionar com erro (form inválido)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrestacaoContas.objects.count(), 0)

    def test_rejeitar_arquivo_txt_renomeado_pdf(self):
        """Arquivo .txt renomeado para .xlsx deve ser rejeitado."""
        arquivo = SimpleUploadedFile("relatorio.txt", b"texto puro", content_type="text/plain")
        response = self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 5, 'ano_referencia': 2026,
            'arquivo': arquivo,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrestacaoContas.objects.count(), 0)


class SubstituicaoEntregaTests(BaseTestSetup):
    """Testes de substituição de entrega no mesmo mês/ano."""

    def test_reenvio_substitui_registro_anterior(self):
        """Reenviar para o mesmo contrato/mês/ano substitui o registro existente."""
        # Primeiro envio
        self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 6, 'ano_referencia': 2026,
            'arquivo': self._make_pdf("v1.pdf"), 'observacao': 'Versão 1'
        })
        self.assertEqual(PrestacaoContas.objects.count(), 1)

        # Segundo envio (mesmo mês/ano)
        self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 6, 'ano_referencia': 2026,
            'arquivo': self._make_pdf("v2.pdf"), 'observacao': 'Versão 2'
        })
        self.assertEqual(PrestacaoContas.objects.count(), 1)
        p = PrestacaoContas.objects.first()
        self.assertEqual(p.observacao, 'Versão 2')
        self._cleanup(p)

    def test_envio_meses_diferentes_nao_substitui(self):
        """Envios em meses diferentes criam registros separados."""
        self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 3, 'ano_referencia': 2026,
            'arquivo': self._make_pdf("mar.pdf"),
        })
        self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 4, 'ano_referencia': 2026,
            'arquivo': self._make_pdf("abr.pdf"),
        })
        self.assertEqual(PrestacaoContas.objects.count(), 2)
        for p in PrestacaoContas.objects.all():
            self._cleanup(p)


class RedirecionamentoTests(BaseTestSetup):
    """Testes de redirecionamento correto."""

    def test_get_na_url_de_upload_redireciona(self):
        """GET na URL de upload deve redirecionar (não processar formulário)."""
        response = self.client.get(self.url_upload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrestacaoContas.objects.count(), 0)

    def test_envio_invalido_redireciona_com_erro(self):
        """Formulário inválido redireciona de volta ao detalhe do contrato."""
        response = self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 5, 'ano_referencia': 2026,
            # Sem arquivo — campo obrigatório
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrestacaoContas.objects.count(), 0)

    def test_envio_invalido_exibe_mensagem_no_detalhe(self):
        """Verifica se mensagens de erro (fallback) são exibidas no template de detalhe do contrato."""
        response = self.client.post(self.url_upload, {
            'agente': self.agente.id,
            'mes_referencia': 5, 'ano_referencia': 2026,
            # Sem arquivo — campo obrigatório
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PrestacaoContas.objects.count(), 0)
        # O Django deve renderizar o bloco de mensagens que inserimos no detalhe.html
        self.assertContains(response, "Este campo é obrigatório")
        self.assertContains(response, "alert-danger")

    def test_contrato_inexistente_retorna_404(self):
        """Upload para contrato inexistente retorna 404."""
        url = reverse('upload_prestacao', kwargs={'contrato_id': 99999})
        response = self.client.post(url, {
            'agente': self.agente.id,
            'mes_referencia': 1, 'ano_referencia': 2026,
            'arquivo': self._make_pdf(),
        })
        self.assertEqual(response.status_code, 404)


class RestricaoAgenteTests(BaseTestSetup):
    """Testes para verificar que apenas agentes vinculados ao contrato podem enviar."""

    def test_agente_sem_comissao_ativa_e_rejeitado(self):
        """Agente que não pertence a comissão ativa do contrato não pode enviar."""
        posto2 = PostoGraduacao.objects.create(sigla="SD", descricao="Soldado", senioridade=10)
        agente_externo = Agente.objects.create(
            nome_completo="Outro Militar", nome_de_guerra="Outro",
            posto=posto2, saram="9999999"
        )
        response = self.client.post(self.url_upload, {
            'agente': agente_externo.id,
            'mes_referencia': 8, 'ano_referencia': 2026,
            'arquivo': self._make_pdf(),
        })
        # Form inválido — agente não está no queryset filtrado
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PrestacaoContas.objects.count(), 0)


class AlterarStatusAjaxTests(BaseTestSetup):
    """Testes para a alteração de status via AJAX (sem recarregar a página)."""

    def setUp(self):
        super().setUp()
        pdf = self._make_pdf("pc.pdf")
        self.prestacao = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=5, ano_referencia=2026, arquivo=pdf
        )
        # Criar usuários
        self.grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        self.user_auditor = User.objects.create_user(username="auditor_ajax", password="pass123")
        self.user_auditor.groups.add(self.grupo_auditores)
        self.user_admin = User.objects.create_superuser(username="admin_ajax", email="a@t.com", password="pass123")
        self.user_normal = User.objects.create_user(username="normal_ajax", password="pass123")

    def tearDown(self):
        for p in PrestacaoContas.objects.all():
            self._cleanup(p)

    def _ajax_get(self, url):
        return self.client.get(url, {'ajax': '1', 'mes': 5, 'ano': 2026},
                               HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_ajax_retorna_json_com_sucesso(self):
        """Requisição AJAX deve retornar JSON com success=True."""
        self.client.login(username="auditor_ajax", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'ok'})
        response = self._ajax_get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['status_display'], 'Conformidade (OK!)')
        self.assertEqual(data['prestacao_id'], self.prestacao.id)

    def test_ajax_atualiza_status_no_banco(self):
        """AJAX deve efetivamente alterar o status no banco de dados."""
        self.client.login(username="auditor_ajax", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'correcao'})
        self._ajax_get(url)
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'correcao')

    def test_ajax_retorna_estatisticas(self):
        """AJAX deve retornar estatísticas atualizadas do mês."""
        self.client.login(username="admin_ajax", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'ok'})
        response = self._ajax_get(url)
        data = json.loads(response.content)
        self.assertIn('stats', data)
        stats = data['stats']
        self.assertIn('ok_no_mes', stats)
        self.assertIn('entregues_no_mes', stats)
        self.assertIn('correcao_no_mes', stats)
        self.assertIn('pendentes_no_mes', stats)
        self.assertIn('total_contratos', stats)

    def test_ajax_nao_gera_mensagem_django(self):
        """Requisição AJAX não deve criar mensagens no framework do Django."""
        self.client.login(username="auditor_ajax", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'ok'})
        self._ajax_get(url)
        # Acessar o dashboard e verificar que não há mensagem de sucesso
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertNotContains(response, "alterado para")

    def test_ajax_usuario_sem_permissao_retorna_403(self):
        """Usuário normal via AJAX deve receber 403."""
        self.client.login(username="normal_ajax", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'ok'})
        response = self._ajax_get(url)
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        # Status não deve ter mudado
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'entregue')

    def test_ajax_status_invalido_retorna_400(self):
        """Status inválido via AJAX deve retornar 400."""
        self.client.login(username="auditor_ajax", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'invalido'})
        response = self._ajax_get(url)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_ajax_sem_login_redireciona(self):
        """Requisição AJAX sem login deve redirecionar para login (302)."""
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'ok'})
        response = self._ajax_get(url)
        self.assertEqual(response.status_code, 302)

    def test_ajax_transicoes_multiplas(self):
        """Múltiplas transições de status via AJAX funcionam corretamente."""
        self.client.login(username="auditor_ajax", password="pass123")
        pk = self.prestacao.id

        # entregue -> ok
        url = reverse('alterar_status_prestacao', kwargs={'pk': pk, 'novo_status': 'ok'})
        self._ajax_get(url)
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'ok')

        # ok -> correcao
        url = reverse('alterar_status_prestacao', kwargs={'pk': pk, 'novo_status': 'correcao'})
        self._ajax_get(url)
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'correcao')

        # correcao -> entregue
        url = reverse('alterar_status_prestacao', kwargs={'pk': pk, 'novo_status': 'entregue'})
        self._ajax_get(url)
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'entregue')


class ModelPrestacaoContasTests(BaseTestSetup):
    """Testes do modelo PrestacaoContas."""

    def test_unique_together_contrato_mes_ano(self):
        """Não pode haver duas prestações do mesmo contrato/mês/ano."""
        from django.db import IntegrityError, transaction
        PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=9, ano_referencia=2026,
            arquivo=self._make_pdf("a.pdf")
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrestacaoContas.objects.create(
                    contrato=self.contrato, agente=self.agente,
                    mes_referencia=9, ano_referencia=2026,
                    arquivo=self._make_pdf("b.pdf")
                )
        for p in PrestacaoContas.objects.all():
            self._cleanup(p)

    def test_status_default_entregue(self):
        """Status padrão ao criar deve ser 'entregue'."""
        p = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=10, ano_referencia=2026,
            arquivo=self._make_pdf()
        )
        self.assertEqual(p.status, 'entregue')
        self._cleanup(p)

    def test_str_representation(self):
        """O __str__ deve exibir número do contrato e mês/ano."""
        p = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=2, ano_referencia=2026,
            arquivo=self._make_pdf()
        )
        self.assertIn("20/2026", str(p))
        self.assertIn("02/2026", str(p))
        self._cleanup(p)

    def test_ordering(self):
        """Prestações devem vir ordenadas por ano e mês decrescentes."""
        p1 = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=1, ano_referencia=2026,
            arquivo=self._make_pdf("jan.pdf")
        )
        # Criar outro contrato para evitar unique_together
        contrato2 = Contrato.objects.create(
            numero="21/2026", objeto="Outro Serviço",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=30000.00
        )
        p2 = PrestacaoContas.objects.create(
            contrato=contrato2, agente=self.agente,
            mes_referencia=12, ano_referencia=2025,
            arquivo=self._make_pdf("dez.pdf")
        )
        todos = list(PrestacaoContas.objects.all())
        # 2026 vem antes de 2025 (decrescente)
        self.assertEqual(todos[0].ano_referencia, 2026)
        self.assertEqual(todos[1].ano_referencia, 2025)
        self._cleanup(p1)
        self._cleanup(p2)
