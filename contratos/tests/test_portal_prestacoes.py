"""
Testes para o Portal Público de Prestações de Contas (v1.6.0).

Cobre:
- Landing page, seleção de contratos e seleção de setores
- Upload de prestação por setor (envio válido, validações, histórico 6 meses)
- Ano renderizado como inteiro (sem separador de milhar) em todos os templates
- Dashboard: aba Setores com matriz de acompanhamento
- Alteração de status de setor (OK, Correção com justificativa, permissões)
- Download e exclusão de prestação de setor
- Desacoplamento: detalhe.html não contém mais formulário de upload
- Isolamento entre setores
"""
import os
import json
from datetime import date, timedelta
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Empresa, PrestacaoContas, PrestacaoContasSetor,
    Agente, PostoGraduacao, Comissao, Integrante, Funcao,
    Setor, CargoRegimental, ApontamentoCorrecaoSetor
)


class BaseSetorTestSetup(TestCase):
    """Setup compartilhado para testes do portal de setores."""

    def setUp(self):
        self.posto = PostoGraduacao.objects.create(sigla="1S", descricao="Primeiro Sargento", senioridade=5)
        self.agente = Agente.objects.create(
            nome_completo="Roberto Silva", nome_de_guerra="Silva",
            posto=self.posto, saram="9988776"
        )
        self.setor = Setor.objects.create(nome="Seção de Informática", sigla="SINF", ordem=1)
        self.cargo = CargoRegimental.objects.create(
            setor=self.setor, agente=self.agente,
            cargo="Chefe", ativo=True
        )
        # Contrato vigente (para testes de fiscais)
        self.empresa = Empresa.objects.create(razao_social="Delta Corp", cnpj="55666777000199")
        self.contrato = Contrato.objects.create(
            numero="50/2026", objeto="TI",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=100000
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO',
            ativa=True, data_inicio=date(2026, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal Técnico", ordem=1)
        Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date(2026, 1, 1),
            portaria_numero="100", portaria_data=date(2026, 1, 1)
        )
        # Usuários
        self.admin_user = User.objects.create_user('admin_test', password='pw')
        self.auditor_user = User.objects.create_user('auditor_test', password='pw')
        self.normal_user = User.objects.create_user('normal_test', password='pw')
        admin_group, _ = Group.objects.get_or_create(name='Administradores')
        auditor_group, _ = Group.objects.get_or_create(name='Auditores')
        self.admin_user.groups.add(admin_group)
        self.auditor_user.groups.add(auditor_group)

        self.client = Client()

    def _make_pdf(self, name="setor.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 test content", content_type="application/pdf")

    def _criar_prestacao_setor(self, mes, ano, status='entregue', setor=None):
        pdf = self._make_pdf(f"pc_setor_{mes}_{ano}.pdf")
        return PrestacaoContasSetor.objects.create(
            setor=setor or self.setor, agente=self.agente,
            mes_referencia=mes, ano_referencia=ano,
            arquivo=pdf, status=status
        )

    def tearDown(self):
        for p in PrestacaoContasSetor.objects.all():
            if p.arquivo:
                try:
                    if os.path.isfile(p.arquivo.path):
                        os.remove(p.arquivo.path)
                except (ValueError, FileNotFoundError):
                    pass
        for p in PrestacaoContas.objects.all():
            if p.arquivo:
                try:
                    if os.path.isfile(p.arquivo.path):
                        os.remove(p.arquivo.path)
                except (ValueError, FileNotFoundError):
                    pass


# ===================================================================
# 1. LANDING PAGE E PÁGINAS DE SELEÇÃO
# ===================================================================
class PortalLandingPageTests(BaseSetorTestSetup):
    """Testes da landing page e páginas de seleção."""

    def test_landing_page_acessivel_sem_login(self):
        response = self.client.get(reverse('portal_prestacao_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fiscais de Contrato")
        self.assertContains(response, "Chefes de Setor")

    def test_pagina_fiscais_lista_contratos_vigentes(self):
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('contratos', response.context)
        self.assertIn(self.contrato, response.context['contratos'])

    def test_pagina_gestores_lista_setores(self):
        response = self.client.get(reverse('portal_prestacao_gestores'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('setores', response.context)
        self.assertIn(self.setor, response.context['setores'])

    def test_contrato_expirado_nao_aparece_na_selecao(self):
        Contrato.objects.create(
            numero="99/2025", objeto="Expirado", empresa=self.empresa,
            vigencia_inicio=date(2025, 1, 1), vigencia_fim=date(2025, 6, 30),
            valor_total=1000
        )
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        numeros = [c.numero for c in response.context['contratos']]
        self.assertNotIn("99/2025", numeros)


# ===================================================================
# 2. UPLOAD DE PRESTAÇÃO POR SETOR
# ===================================================================
class UploadPrestacaoSetorTests(BaseSetorTestSetup):
    """Testes do envio de prestação de contas por setor."""

    def test_envio_valido_sem_login(self):
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.post(url, {
            'agente': self.agente.id,
            'mes_referencia': 4, 'ano_referencia': 2026,
            'arquivo': self._make_pdf(), 'observacao': 'Envio abril'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("?enviado=1", response.url)
        self.assertEqual(PrestacaoContasSetor.objects.count(), 1)
        p = PrestacaoContasSetor.objects.first()
        self.assertEqual(p.mes_referencia, 4)
        self.assertEqual(p.ano_referencia, 2026)
        self.assertEqual(p.status, 'entregue')

    def test_envio_rejeita_arquivo_nao_pdf(self):
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        arquivo = SimpleUploadedFile("doc.txt", b"texto", content_type="text/plain")
        response = self.client.post(url, {
            'agente': self.agente.id,
            'mes_referencia': 4, 'ano_referencia': 2026,
            'arquivo': arquivo
        })
        self.assertEqual(PrestacaoContasSetor.objects.count(), 0)

    def test_envio_rejeita_arquivo_maior_que_10mb(self):
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        big_pdf = SimpleUploadedFile("big.pdf", b"%" * (11 * 1024 * 1024), content_type="application/pdf")
        response = self.client.post(url, {
            'agente': self.agente.id,
            'mes_referencia': 4, 'ano_referencia': 2026,
            'arquivo': big_pdf
        })
        self.assertEqual(PrestacaoContasSetor.objects.count(), 0)

    def test_setor_inexistente_retorna_404(self):
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_carrega_formulario_e_historico(self):
        self._criar_prestacao_setor(3, 2026)
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('historico', response.context)
        self.assertEqual(len(response.context['historico']), 1)

    def test_envio_ajax_retorna_json_sucesso(self):
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.post(url, {
            'agente': self.agente.id,
            'mes_referencia': 4, 'ano_referencia': 2026,
            'arquivo': self._make_pdf()
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])


# ===================================================================
# 3. HISTÓRICO DE ENVIOS DO SETOR (6 MESES)
# ===================================================================
class HistoricoSetorTests(BaseSetorTestSetup):
    """Testes do histórico de últimos envios do setor."""

    def test_limite_maximo_6_prestacoes(self):
        for mes in range(1, 9):
            self._criar_prestacao_setor(mes, 2026)
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.get(url)
        self.assertEqual(len(response.context['historico']), 6)

    def test_ordenacao_decrescente(self):
        self._criar_prestacao_setor(1, 2026)
        self._criar_prestacao_setor(3, 2026)
        self._criar_prestacao_setor(5, 2026)
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.get(url)
        periodos = [(p.mes_referencia, p.ano_referencia) for p in response.context['historico']]
        self.assertEqual(periodos, [(5, 2026), (3, 2026), (1, 2026)])

    def test_exclui_pendentes(self):
        self._criar_prestacao_setor(1, 2026, status='entregue')
        self._criar_prestacao_setor(2, 2026, status='pendente')
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.get(url)
        meses = [p.mes_referencia for p in response.context['historico']]
        self.assertIn(1, meses)
        self.assertNotIn(2, meses)

    def test_isolamento_entre_setores(self):
        outro_setor = Setor.objects.create(nome="Seção de Pessoal", sigla="SP", ordem=2)
        self._criar_prestacao_setor(5, 2026, setor=outro_setor)
        self._criar_prestacao_setor(5, 2026, setor=self.setor)
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.get(url)
        self.assertEqual(len(response.context['historico']), 1)
        self.assertEqual(response.context['historico'][0].setor, self.setor)


# ===================================================================
# 4. ANO COMO INTEIRO (SEM SEPARADOR DE MILHAR)
# ===================================================================
class AnoInteiroTests(BaseSetorTestSetup):
    """Verifica que o ano é renderizado como inteiro (2026) e não '2.026'."""

    def test_ano_inteiro_no_upload_contrato(self):
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertNotContains(response, "2.026")

    def test_ano_inteiro_no_upload_setor(self):
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.get(url)
        self.assertNotContains(response, "2.026")

    def test_ano_inteiro_no_historico_upload_contrato(self):
        """Cria prestação e verifica se o ano no histórico não tem ponto."""
        pdf = self._make_pdf("c.pdf")
        PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=3, ano_referencia=2026,
            arquivo=pdf, status='entregue'
        )
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertContains(response, "03/2026")
        self.assertNotContains(response, "2.026")

    def test_ano_inteiro_no_historico_upload_setor(self):
        self._criar_prestacao_setor(3, 2026)
        url = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response = self.client.get(url)
        self.assertContains(response, "03/2026")
        self.assertNotContains(response, "2.026")

    def test_ano_inteiro_no_dashboard_matriz(self):
        self.client.login(username='auditor_test', password='pw')
        response = self.client.get(reverse('dashboard_prestacao'))
        content = response.content.decode()
        self.assertNotIn("2.026", content)

    def test_ano_inteiro_no_detalhe_contrato(self):
        """O detalhe público do contrato não deve ter ponto no ano."""
        url = reverse('detalhe_contrato', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        # A view já não passa prestações, mas o ano do contrato pode aparecer
        self.assertNotContains(response, "2.026")


# ===================================================================
# 5. DASHBOARD — ABA SETORES
# ===================================================================
class DashboardSetoresTests(BaseSetorTestSetup):
    """Testes da aba Setores no dashboard de auditoria."""

    def test_dashboard_requer_login(self):
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_contem_matriz_setores(self):
        self.client.login(username='auditor_test', password='pw')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertIn('matriz_setores', response.context)

    def test_aba_setores_visivel_no_html(self):
        self.client.login(username='auditor_test', password='pw')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertContains(response, "Setores")
        self.assertContains(response, "setores-pane")

    def test_matriz_setores_lista_todos_os_setores(self):
        Setor.objects.create(nome="Outro Setor", sigla="OS", ordem=2)
        self.client.login(username='auditor_test', password='pw')
        response = self.client.get(reverse('dashboard_prestacao'))
        siglas = [s['setor'].sigla for s in response.context['matriz_setores']]
        self.assertIn("SINF", siglas)
        self.assertIn("OS", siglas)

    def test_matriz_setores_mostra_status_entregue(self):
        hoje = date.today()
        mes_ant = (hoje.replace(day=1) - timedelta(days=1)).month
        ano_ant = (hoje.replace(day=1) - timedelta(days=1)).year
        self._criar_prestacao_setor(mes_ant, ano_ant, status='entregue')
        self.client.login(username='auditor_test', password='pw')
        response = self.client.get(reverse('dashboard_prestacao'))
        found = False
        for s_data in response.context['matriz_setores']:
            if s_data['setor'].id == self.setor.id:
                for e in s_data['entregas']:
                    if e['mes'] == mes_ant and e['ano'] == ano_ant:
                        self.assertEqual(e['status'], 'entregue')
                        found = True
        self.assertTrue(found, "Não encontrou a entrega do setor na matriz")


# ===================================================================
# 6. ALTERAÇÃO DE STATUS (SETOR)
# ===================================================================
class AlterarStatusSetorTests(BaseSetorTestSetup):
    """Testes de alteração de status de prestação de setor."""

    def test_aprovar_ok(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='auditor_test', password='pw')
        url = reverse('alterar_status_prestacao_setor', kwargs={'pk': p.id, 'novo_status': 'ok'})
        response = self.client.get(url)
        p.refresh_from_db()
        self.assertEqual(p.status, 'ok')

    def test_correcao_requer_justificativa(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='auditor_test', password='pw')
        url = reverse('alterar_status_prestacao_setor', kwargs={'pk': p.id, 'novo_status': 'correcao'})
        # Sem justificativa — deve redirecionar sem alterar status
        response = self.client.get(url)
        p.refresh_from_db()
        self.assertNotEqual(p.status, 'correcao')

    def test_correcao_com_justificativa_cria_apontamento(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='auditor_test', password='pw')
        url = reverse('alterar_status_prestacao_setor', kwargs={'pk': p.id, 'novo_status': 'correcao'})
        response = self.client.post(url, data={'justificativa': 'Faltou capa'})
        p.refresh_from_db()
        self.assertEqual(p.status, 'correcao')
        self.assertEqual(ApontamentoCorrecaoSetor.objects.filter(prestacao=p).count(), 1)

    def test_usuario_sem_permissao_nao_altera_status(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='normal_test', password='pw')
        url = reverse('alterar_status_prestacao_setor', kwargs={'pk': p.id, 'novo_status': 'ok'})
        response = self.client.get(url)
        p.refresh_from_db()
        self.assertEqual(p.status, 'entregue')

    def test_status_invalido_rejeitado(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='auditor_test', password='pw')
        url = reverse('alterar_status_prestacao_setor', kwargs={'pk': p.id, 'novo_status': 'invalido'})
        response = self.client.get(url)
        p.refresh_from_db()
        self.assertEqual(p.status, 'entregue')


# ===================================================================
# 7. DOWNLOAD E EXCLUSÃO (SETOR)
# ===================================================================
class DownloadExcluirSetorTests(BaseSetorTestSetup):
    """Testes de download e exclusão de prestação de setor."""

    def test_download_requer_login(self):
        p = self._criar_prestacao_setor(4, 2026)
        url = reverse('download_prestacao_setor', kwargs={'pk': p.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_download_retorna_pdf(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='auditor_test', password='pw')
        url = reverse('download_prestacao_setor', kwargs={'pk': p.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_exclusao_requer_admin(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='auditor_test', password='pw')
        url = reverse('excluir_prestacao_setor', kwargs={'pk': p.id})
        response = self.client.post(url)
        self.assertTrue(PrestacaoContasSetor.objects.filter(pk=p.id).exists())

    def test_admin_pode_excluir(self):
        p = self._criar_prestacao_setor(4, 2026)
        self.client.login(username='admin_test', password='pw')
        url = reverse('excluir_prestacao_setor', kwargs={'pk': p.id})
        response = self.client.post(url)
        self.assertFalse(PrestacaoContasSetor.objects.filter(pk=p.id).exists())


# ===================================================================
# 8. DESACOPLAMENTO DO DETALHE.HTML
# ===================================================================
class DesacoplamentoDetalheTests(BaseSetorTestSetup):
    """Verifica que detalhe.html não contém mais o formulário de upload."""

    def test_detalhe_nao_contem_formulario_upload(self):
        url = reverse('detalhe_contrato', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertNotContains(response, "form-upload-prestacao")
        self.assertNotContains(response, "Enviar Arquivo")
        self.assertNotContains(response, "Enviar Relatório")

    def test_detalhe_nao_contem_secao_prestacao_contas_mensal(self):
        url = reverse('detalhe_contrato', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertNotContains(response, "Prestação de Contas Mensal")
