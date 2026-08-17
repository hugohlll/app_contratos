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
    Setor, CargoRegimental, ApontamentoCorrecaoSetor, ApontamentoCorrecao,
    CalendarioPrestacao, ControleExecucao
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
        self.assertNotContains(response, "Controle de Execução Contratual (Livro do Fiscal)")

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

    def test_landing_page_exibe_calendario_mes_anterior(self):
        """A landing page deve mostrar o calendário do mês anterior ao atual."""
        from datetime import date
        hoje = date.today()
        if hoje.month == 1:
            mes = 12
            ano = hoje.year - 1
        else:
            mes = hoje.month - 1
            ano = hoje.year
            
        # Cria o calendário esperado
        cal = CalendarioPrestacao.objects.create(
            mes=mes, ano=ano,
            data_entrega=date(ano, mes, 5),
            data_apresentacao_fiscais=date(ano, mes, 10),
            data_apresentacao_gestores=date(ano, mes, 15)
        )
        
        response = self.client.get(reverse('portal_prestacao_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('calendario', response.context)
        self.assertEqual(response.context['calendario'], cal)
        # Check date string formatting is present in the rendered HTML (e.g., 05/...)
        self.assertContains(response, cal.data_entrega.strftime('%d/%m/%Y'))

    def test_landing_page_calendario_nao_cadastrado_mostra_a_definir(self):
        """Se o calendário do mês anterior não existir, deve exibir 'A definir'."""
        CalendarioPrestacao.objects.all().delete()
        response = self.client.get(reverse('portal_prestacao_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['calendario'])
        self.assertContains(response, "A definir", count=3)


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
        """Cria prestação e verifica se o ano no painel do contrato não tem ponto."""
        hoje = date.today()
        ultimo_dia_mes_ant = hoje.replace(day=1) - timedelta(days=1)
        mes = ultimo_dia_mes_ant.month
        ano = ultimo_dia_mes_ant.year
        pdf = self._make_pdf("c.pdf")
        PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=mes, ano_referencia=ano,
            arquivo=pdf, status='entregue'
        )
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertContains(response, f"{mes:02d}/{ano}")
        self.assertNotContains(response, f"{ano // 1000}.{ano % 1000:03d}")

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

    def test_ano_inteiro_na_landing_page(self):
        """A landing page deve mostrar o ano sem ponto (ex: 2026 e não 2.026)."""
        response = self.client.get(reverse('portal_prestacao_index'))
        self.assertNotContains(response, "2.026")

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

# ===================================================================
# 9. TEXTOS E NOMENCLATURAS
# ===================================================================
class TextoApontamentosTests(BaseSetorTestSetup):
    """Verifica alterações textuais nos templates de upload."""

    def test_texto_apontamentos_aci_nos_uploads(self):
        """Os templates de upload devem exibir 'Apontamentos da ACI' ao invés de 'Auditoria'."""
        # Testando para contrato
        pdf = self._make_pdf("c.pdf")
        p_contrato = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=3, ano_referencia=2026,
            arquivo=pdf, status='correcao'
        )
        ApontamentoCorrecao.objects.create(
            prestacao=p_contrato, autor=self.admin_user, descricao="Erro"
        )
        url_contrato = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}) + "?mes=3&ano=2026"
        response_c = self.client.get(url_contrato)
        self.assertContains(response_c, "Apontamentos da ACI")

        # Testando para setor
        p_setor = self._criar_prestacao_setor(3, 2026, status='correcao')
        ApontamentoCorrecaoSetor.objects.create(
            prestacao=p_setor, autor=self.admin_user, descricao="Erro setor"
        )
        url_setor = reverse('upload_prestacao_setor', kwargs={'setor_id': self.setor.id})
        response_s = self.client.get(url_setor)
        self.assertContains(response_s, "Apontamentos da ACI:")

    def test_chat_layout_fiscal_esquerda_aci_direita(self):
        """Verifica alinhamento de balões do chat: Fiscal à esquerda e ACI à direita."""
        from contratos.models import ControleExecucao, ApontamentoCorrecaoExecucao
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        m_ref = ultimo_dia_mes_anterior.month
        a_ref = ultimo_dia_mes_anterior.year

        # 1. Criar Livro do Fiscal com observação
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=m_ref,
            ano_referencia=a_ref,
            status='correcao',
            observacao="Dúvida referente ao item 4 do cronograma."
        )

        # 2. Criar Apontamento da ACI
        ApontamentoCorrecaoExecucao.objects.create(
            controle=ctrl,
            autor=self.admin_user,
            descricao="Solicitamos adequação das datas conforme termo aditivo."
        )

        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        # Deve ter container do chat
        self.assertContains(res, "dialogo-chat")
        # Balão do Fiscal à esquerda
        self.assertContains(res, "justify-content-start")
        self.assertContains(res, "Dúvida referente ao item 4 do cronograma.")
        # Balão da ACI à direita
        self.assertContains(res, "justify-content-end")
        self.assertContains(res, "Solicitamos adequação das datas conforme termo aditivo.")

    def test_envio_sem_observacao_nao_gera_balao_vazio(self):
        """Verifica que envios sem observações não geram balões vazios no chat."""
        from contratos.models import ControleExecucao
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        m_ref = ultimo_dia_mes_anterior.month
        a_ref = ultimo_dia_mes_anterior.year

        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=m_ref,
            ano_referencia=a_ref,
            status='entregue',
            observacao=""  # Sem observações
        )

        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "dialogo-chat")

    def test_livro_fiscal_multiplas_observacoes_historico_cronologico(self):
        """Verifica se múltiplas observações do fiscal e apontamentos da ACI são ordenados cronologicamente."""
        from contratos.models import ControleExecucao, ApontamentoCorrecaoExecucao, HistoricoObservacaoExecucao
        from django.utils import timezone

        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        m_ref = ultimo_dia_mes_anterior.month
        a_ref = ultimo_dia_mes_anterior.year

        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=m_ref,
            ano_referencia=a_ref,
            status='correcao',
            observacao="Obs 1 inicial"
        )

        agora = timezone.now()
        t1 = agora - timedelta(hours=3)
        t2 = agora - timedelta(hours=2)
        t3 = agora - timedelta(hours=1)

        # 1. Primeira obs do fiscal at t1
        obs1 = HistoricoObservacaoExecucao.objects.create(
            controle=ctrl, agente=self.agente, observacao="Obs 1 inicial"
        )
        obs1.data_envio = t1
        obs1.save()

        # 2. Apontamento ACI at t2
        apt = ApontamentoCorrecaoExecucao.objects.create(
            controle=ctrl, autor=self.admin_user, descricao="Apontamento ACI 1"
        )
        apt.data_registro = t2
        apt.save()

        # 3. Segunda obs do fiscal at t3 (resposta ao apontamento)
        obs2 = HistoricoObservacaoExecucao.objects.create(
            controle=ctrl, agente=self.agente, observacao="Obs 2 resposta conforme solicitado"
        )
        obs2.data_envio = t3
        obs2.save()

        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        chat_idx = content.find("dialogo-chat")
        self.assertNotEqual(chat_idx, -1)
        chat_content = content[chat_idx:]

        pos_obs1 = chat_content.find("Obs 1 inicial")
        pos_aci1 = chat_content.find("Apontamento ACI 1")
        pos_obs2 = chat_content.find("Obs 2 resposta conforme solicitado")

        self.assertNotEqual(pos_obs1, -1)
        self.assertNotEqual(pos_aci1, -1)
        self.assertNotEqual(pos_obs2, -1)
        # Garante ordem cronológica exata: Obs 1 < Apontamento 1 < Obs 2
        self.assertTrue(pos_obs1 < pos_aci1 < pos_obs2)

    def test_slides_multiplas_observacoes_historico_cronologico(self):
        """Verifica ordem cronológica para histórico de slides em múltiplas rodadas."""
        from contratos.models import PrestacaoContas, ApontamentoCorrecao
        from django.utils import timezone

        agora = timezone.now()
        t1 = agora - timedelta(hours=3)
        t2 = agora - timedelta(hours=2)
        t3 = agora - timedelta(hours=1)

        pdf1 = self._make_pdf("s1.pdf")
        pdf2 = self._make_pdf("s2.pdf")

        p1 = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=3, ano_referencia=2026,
            arquivo=pdf1, status='correcao', observacao="Envio de slides v1"
        )
        p1.data_envio = t1
        p1.save()

        apt = ApontamentoCorrecao.objects.create(
            prestacao=p1, autor=self.admin_user, descricao="Ajustar slide 3"
        )
        apt.data_registro = t2
        apt.save()

        p2 = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=3, ano_referencia=2026,
            arquivo=pdf2, status='entregue', observacao="Envio de slides v2 corrigido"
        )
        p2.data_envio = t3
        p2.save()

        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}) + "?mes=3&ano=2026"
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        pos_v1 = content.find("Envio de slides v1")
        pos_aci = content.find("Ajustar slide 3")
        pos_v2 = content.find("Envio de slides v2 corrigido")

        self.assertNotEqual(pos_v1, -1)
        self.assertNotEqual(pos_aci, -1)
        self.assertNotEqual(pos_v2, -1)
        self.assertTrue(pos_v1 < pos_aci < pos_v2)

    def test_fallback_observacao_legado_controle_execucao(self):
        """Garante fallback para observacao legada se não houver histórico dedicado."""
        from contratos.models import ControleExecucao
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        m_ref = ultimo_dia_mes_anterior.month
        a_ref = ultimo_dia_mes_anterior.year

        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=m_ref,
            ano_referencia=a_ref,
            status='entregue',
            observacao="Observacao legada anterior"
        )

        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Observacao legada anterior")


# ===================================================================
# 10. FILTROS DE BUSCA E STATUS NA MATRIZ DO DASHBOARD
# ===================================================================
class FiltrosMatrizDashboardTests(BaseSetorTestSetup):
    """Verifica se os campos de busca, filtros de status e sub-abas estão presentes na matriz do dashboard."""

    def test_elementos_de_filtro_e_subabas_no_dashboard(self):
        self.client.force_login(self.admin_user)
        url = reverse('dashboard_prestacao')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Abas principais
        self.assertContains(response, 'id="fiscais-tab"')
        self.assertContains(response, 'id="setores-tab"')
        self.assertContains(response, 'id="calendario-tab"')

        # Sub-abas internas da aba Fiscais (Slides vs Livro do Fiscal)
        self.assertContains(response, 'id="fiscaisSubTabs"')
        self.assertContains(response, 'id="fiscais-slides-subtab"')
        self.assertContains(response, 'id="fiscais-execucao-subtab"')
        self.assertContains(response, 'id="fiscais-slides-subpane"')

        # Filtros da matriz de Fiscais
        self.assertContains(response, 'id="filtroMatrizFiscais"')
        self.assertContains(response, 'id="filtroMatrizFiscaisStatus"')

        # Filtros da matriz do Livro do Fiscal (Execução)
        self.assertContains(response, 'id="filtroMatrizExecucao"')
        self.assertContains(response, 'id="filtroMatrizExecucaoStatus"')
        self.assertContains(response, 'linha-matriz-execucao')


# ===================================================================
# 11. REENGENHARIA DASHBOARD — SUB-ABAS E HISTÓRICO DE 6 MESES
# ===================================================================
class DashboardReengenhariaSubAbasTests(BaseSetorTestSetup):
    """Testes para a reengenharia do Dashboard (sub-abas e histórico de 6 meses)."""

    def test_dashboard_contem_novas_subabas_fiscais_e_setores(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)

        # Novas sub-abas da aba Fiscais
        self.assertContains(response, 'id="fiscais-mes-subtab"')
        self.assertContains(response, 'id="fiscais-slides-subtab"')
        self.assertContains(response, 'id="fiscais-execucao-subtab"')

        # Novas sub-abas da aba Setores
        self.assertContains(response, 'id="setores-mes-subtab"')
        self.assertContains(response, 'id="setores-matriz-subtab"')

    def test_contexto_retorna_ultimos_6_meses(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)

        self.assertIn('ultimos_6_meses_tuplas', response.context)
        ultimos_6_meses = response.context['ultimos_6_meses_tuplas']
        self.assertEqual(len(ultimos_6_meses), 6)

    def test_entregas_mes_selecionado_unificado(self):
        # Cria uma prestação de contas (slides) para o mês corrente/selecionado
        hoje = date.today()
        mes_atual = hoje.month
        ano_atual = hoje.year

        # Cria prestação
        pdf = self._make_pdf("c.pdf")
        prestacao = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=mes_atual, ano_referencia=ano_atual,
            arquivo=pdf, status='entregue', observacao="Relatorio de teste"
        )
        
        # Cria apontamento para a prestação
        ApontamentoCorrecao.objects.create(
            prestacao=prestacao, autor=self.admin_user, descricao="Corrigir slides"
        )

        # Cria controle de execução (Livro do Fiscal)
        controle = ControleExecucao.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=mes_atual, ano_referencia=ano_atual,
            status='ok'
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard_prestacao') + f"?mes={mes_atual}&ano={ano_atual}")
        self.assertEqual(response.status_code, 200)

        # Verifica se os dados unificados do mês selecionado estão corretos no contexto
        self.assertIn('entregas_mes_selecionado', response.context)
        entregas_mes = response.context['entregas_mes_selecionado']
        
        # Procura pelo nosso contrato
        dados_contrato = next((x for x in entregas_mes if x['contrato'] == self.contrato), None)
        self.assertIsNotNone(dados_contrato)
        self.assertEqual(dados_contrato['prestacao'], prestacao)
        self.assertEqual(dados_contrato['controle'], controle)
        self.assertEqual(dados_contrato['status_prestacao'], 'entregue')
        self.assertEqual(dados_contrato['status_controle'], 'ok')
        self.assertIsNotNone(dados_contrato['msg_slides'])
        self.assertEqual(dados_contrato['msg_slides']['texto'], "Corrigir slides")

    def test_dashboard_3_colunas_layout_e_switch(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)

        # HTML table headers: should contain exactly "Contrato / Empresa", "Slides", "Livro do Fiscal"
        # and should not contain the old 4th column header or old name
        self.assertContains(response, 'Contrato / Empresa')
        self.assertContains(response, '<th class="text-center" style="width: 40%;">Slides</th>')
        self.assertContains(response, '<th class="text-center" style="width: 40%;">Livro do Fiscal</th>')
        self.assertNotContains(response, 'Observações do Fiscal & Apontamentos da ACI')

        # Check for prioritário switch component attributes
        self.assertContains(response, 'role="switch"')
        self.assertContains(response, 'class="form-check-input checkbox-apresentacao cursor-pointer"')

    def test_dashboard_livro_fiscal_icons_and_links(self):
        # Create a controle execucao (Livro do Fiscal) in 'ok' status
        hoje = date.today()
        controle_ok = ControleExecucao.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=hoje.month, ano_referencia=hoje.year,
            status='ok'
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dashboard_prestacao') + f"?mes={hoje.month}&ano={hoje.year}")
        self.assertEqual(response.status_code, 200)

        # Should render book check icon and "Conformidade" link pointing to details
        self.assertContains(response, 'bi-journal-check')
        self.assertContains(response, 'Conformidade')
        self.assertContains(response, reverse('visualizar_controle_execucao', args=[controle_ok.id]))

        # The old button and badge styles should not exist
        self.assertNotContains(response, 'class="badge bg-success"><i class="bi bi-check-circle me-1"></i>OK')
        self.assertNotContains(response, 'class="btn btn-sm btn-outline-primary py-0 px-2" title="Visualizar Livro"')

        # Now change status to 'correcao'
        controle_ok.status = 'correcao'
        controle_ok.save()
        response = self.client.get(reverse('dashboard_prestacao') + f"?mes={hoje.month}&ano={hoje.year}")
        self.assertContains(response, 'bi-exclamation-triangle-fill')
        self.assertContains(response, 'Corrigir')

        # Now change status to 'entregue'
        controle_ok.status = 'entregue'
        controle_ok.save()
        response = self.client.get(reverse('dashboard_prestacao') + f"?mes={hoje.month}&ano={hoje.year}")
        self.assertContains(response, 'bi-journal-arrow-up')
        self.assertContains(response, 'Entregue')

    def test_observacoes_livro_fiscal_exibidas_no_dashboard_e_visualizar(self):
        """Verifica se observações do Livro do Fiscal aparecem no Acompanhamento Detalhado do Dashboard e na tela Visualizar."""
        from contratos.models import ControleExecucao, HistoricoObservacaoExecucao

        self.client.force_login(self.admin_user)

        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=3,
            ano_referencia=2026,
            status='entregue',
            observacao="Obs Inicial Legada"
        )
        HistoricoObservacaoExecucao.objects.create(
            controle=ctrl,
            agente=self.agente,
            observacao="Resposta Detalhada do Fiscal do Livro"
        )

        # 1. Dashboard - Acompanhamento Detalhado
        url_dash = reverse('dashboard_prestacao') + "?mes=3&ano=2026"
        res_dash = self.client.get(url_dash)
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, "Resposta Detalhada do Fiscal do Livro")

        # 2. Tela Visualizar Livro do Fiscal (não deve conter observações ou histórico)
        url_vis = reverse('visualizar_controle_execucao', kwargs={'pk': ctrl.id})
        res_vis = self.client.get(url_vis)
        self.assertEqual(res_vis.status_code, 200)
        self.assertNotContains(res_vis, "OBSERVAÇÕES E RESPOSTAS DO FISCAL")

    def test_apenas_mensagem_mais_recente_exibida_no_acompanhamento_detalhado(self):
        """Verifica se apenas a mensagem mais recente (entre ACI e Fiscal/Gestor) é exibida no Acompanhamento Detalhado."""
        import time
        from contratos.models import ControleExecucao, HistoricoObservacaoExecucao, ApontamentoCorrecaoExecucao

        self.client.force_login(self.admin_user)

        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=4,
            ano_referencia=2026,
            status='correcao',
            observacao="Primeira observacao fiscal antiga"
        )
        time.sleep(0.01)
        apt1 = ApontamentoCorrecaoExecucao.objects.create(
            controle=ctrl,
            autor=self.admin_user,
            descricao="Apontamento ACI intermediario"
        )
        time.sleep(0.01)
        obs_rec = HistoricoObservacaoExecucao.objects.create(
            controle=ctrl,
            agente=self.agente,
            observacao="Resposta mais recente do fiscal 123"
        )

        url_dash = reverse('dashboard_prestacao') + "?mes=4&ano=2026"
        res_dash = self.client.get(url_dash)
        self.assertEqual(res_dash.status_code, 200)

        # Deve conter a resposta mais recente do fiscal
        self.assertContains(res_dash, "Resposta mais recente do fiscal 123")

        # Não deve conter o apontamento ACI antigo nem a primeira obs antiga
        self.assertNotContains(res_dash, "Apontamento ACI intermediario")
        self.assertNotContains(res_dash, "Primeira observacao fiscal antiga")


