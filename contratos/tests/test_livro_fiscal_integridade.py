"""
Testes de integridade do Livro do Fiscal: exclusão, edição após ateste,
declaração de período sem ocorrências e ações da ACI apenas via POST.
"""
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Empresa, Agente, PostoGraduacao, ControleExecucao,
    OcorrenciaContratual, Comissao, Integrante, Funcao
)


class LivroFiscalIntegridadeTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.group_auditor = Group.objects.create(name='Auditores')
        self.user_auditor = User.objects.create_user(username='auditor_integridade', password='pwd123')
        self.user_auditor.groups.add(self.group_auditor)

        self.posto = PostoGraduacao.objects.create(sigla="Cap", descricao="Capitão", senioridade=3)
        self.agente = Agente.objects.create(
            nome_completo="Fiscal Integridade Teste",
            nome_de_guerra="Integridade",
            posto=self.posto,
            saram="556677",
        )
        self.empresa = Empresa.objects.create(razao_social="Empresa Integridade", cnpj="22.333.444/0001-55")
        self.contrato = Contrato.objects.create(
            numero="200/2026",
            objeto="Serviços de Manutenção",
            tipo="DESPESA",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2027, 12, 31),
            valor_total=80000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO', ativa=True, data_inicio=date(2026, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal Titular", sigla="FT")
        Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date(2026, 1, 1), portaria_numero="200", portaria_data=date(2026, 1, 1)
        )

        hoje = timezone.localdate()
        mes_anterior = hoje.replace(day=1) - timedelta(days=1)
        self.mes_ant, self.ano_ant = mes_anterior.month, mes_anterior.year
        # Três meses atrás: fora da janela de edição (mês anterior e mês corrente)
        antigo = (mes_anterior.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)
        self.mes_antigo, self.ano_antigo = antigo.month, antigo.year

    def _criar_livro(self, status, mes=None, ano=None, **kwargs):
        return ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=mes or self.mes_ant,
            ano_referencia=ano or self.ano_ant,
            status=status,
            **kwargs
        )

    def _url_formulario(self, mes, ano):
        return reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id}) + f"?mes={mes}&ano={ano}"

    def _payload(self, mes, ano, **extra):
        data = {
            'mes_referencia': mes,
            'ano_referencia': ano,
            'agente': self.agente.id,
            'omap': 'GAP-BR',
            'unidade_gestora': '120006 - GAP-BR',
            'acao': 'finalizar',
        }
        data.update(extra)
        return data

    # --- Correção 1: exclusão pública ---

    def test_exclusao_publica_exige_post(self):
        self._criar_livro('rascunho')
        url = reverse('excluir_controle_execucao_publico', kwargs={'contrato_id': self.contrato.id})
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(ControleExecucao.objects.count(), 1)

    def test_exclusao_publica_bloqueada_para_livro_atestado(self):
        url = reverse('excluir_controle_execucao_publico', kwargs={'contrato_id': self.contrato.id})
        for status in ('entregue', 'ok'):
            livro = self._criar_livro(status)
            OcorrenciaContratual.objects.create(controle=livro, descricao='Ocorrência preservada.')
            res = self.client.post(url)
            self.assertEqual(res.status_code, 302)
            self.assertTrue(ControleExecucao.objects.filter(pk=livro.pk).exists(), status)
            self.assertEqual(livro.ocorrencias.count(), 1, status)
            livro.delete()

    def test_exclusao_publica_permitida_para_rascunho(self):
        self._criar_livro('rascunho')
        url = reverse('excluir_controle_execucao_publico', kwargs={'contrato_id': self.contrato.id})
        self.client.post(url)
        self.assertEqual(ControleExecucao.objects.count(), 0)

    # --- Correção 2: edição após ateste e período permitido ---

    def test_livro_entregue_exibido_somente_leitura(self):
        self._criar_livro('entregue')
        res = self.client.get(self._url_formulario(self.mes_ant, self.ano_ant))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['somente_leitura'])
        self.assertContains(res, 'Livro do Fiscal disponível somente para leitura.')
        self.assertNotContains(res, 'id="btnFinalizarLivro"')
        self.assertNotContains(res, 'id="btnSalvarRascunho"')

    def test_post_em_livro_entregue_nao_altera(self):
        livro = self._criar_livro('entregue', observacao='Texto original atestado.')
        res = self.client.post(
            self._url_formulario(self.mes_ant, self.ano_ant),
            self._payload(self.mes_ant, self.ano_ant, observacao='Texto alterado após ateste.', acao='rascunho')
        )
        self.assertEqual(res.status_code, 302)
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'entregue')
        self.assertEqual(livro.observacao, 'Texto original atestado.')

    def test_livro_em_correcao_continua_editavel(self):
        livro = self._criar_livro('correcao')
        res = self.client.post(
            self._url_formulario(self.mes_ant, self.ano_ant),
            self._payload(self.mes_ant, self.ano_ant, observacao='Corrigido.', sem_ocorrencias_periodo='on')
        )
        self.assertEqual(res.status_code, 302)
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'entregue')
        self.assertEqual(livro.observacao, 'Corrigido.')

    def test_livro_em_correcao_de_mes_antigo_continua_editavel(self):
        livro = self._criar_livro('correcao', mes=self.mes_antigo, ano=self.ano_antigo)
        res = self.client.post(
            self._url_formulario(self.mes_antigo, self.ano_antigo),
            self._payload(self.mes_antigo, self.ano_antigo, observacao='Corrigido tardiamente.', sem_ocorrencias_periodo='on')
        )
        self.assertEqual(res.status_code, 302)
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'entregue')

    def test_criacao_em_mes_fora_da_janela_bloqueada(self):
        res = self.client.post(
            self._url_formulario(self.mes_antigo, self.ano_antigo),
            self._payload(self.mes_antigo, self.ano_antigo, sem_ocorrencias_periodo='on')
        )
        self.assertRedirects(
            res, reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}), fetch_redirect_response=False
        )
        self.assertFalse(ControleExecucao.objects.exists())

    def test_rascunho_em_mes_fora_da_janela_somente_leitura(self):
        livro = self._criar_livro('rascunho', mes=self.mes_antigo, ano=self.ano_antigo, observacao='Original.')
        self.client.post(
            self._url_formulario(self.mes_antigo, self.ano_antigo),
            self._payload(self.mes_antigo, self.ano_antigo, observacao='Alterado.', sem_ocorrencias_periodo='on')
        )
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'rascunho')
        self.assertEqual(livro.observacao, 'Original.')

    # --- Correção 3: "sem ocorrências" não apaga registros ---

    def test_sem_ocorrencias_com_ocorrencias_registradas_e_recusado(self):
        livro = self._criar_livro('rascunho')
        OcorrenciaContratual.objects.create(controle=livro, descricao='Atraso na entrega do material.')
        res = self.client.post(
            self._url_formulario(self.mes_ant, self.ano_ant),
            self._payload(self.mes_ant, self.ano_ant, sem_ocorrencias_periodo='on'),
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Existem 1 ocorrência(s) registrada(s) neste mês.')
        livro.refresh_from_db()
        self.assertEqual(livro.ocorrencias.count(), 1)
        self.assertEqual(livro.status, 'rascunho')
        self.assertFalse(livro.sem_ocorrencias_periodo)

    def test_sem_ocorrencias_sem_registros_finaliza(self):
        livro = self._criar_livro('rascunho')
        res = self.client.post(
            self._url_formulario(self.mes_ant, self.ano_ant),
            self._payload(self.mes_ant, self.ano_ant, sem_ocorrencias_periodo='on')
        )
        self.assertEqual(res.status_code, 302)
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'entregue')
        self.assertTrue(livro.sem_ocorrencias_periodo)

    # --- Correção 4: ações da ACI e do administrador apenas via POST ---

    def test_homologacao_por_get_nao_altera_status(self):
        livro = self._criar_livro('entregue')
        self.client.force_login(self.user_auditor)
        url = reverse('alterar_status_execucao', kwargs={'pk': livro.pk, 'novo_status': 'ok'})
        self.assertEqual(self.client.get(url).status_code, 405)
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'entregue')

        self.client.post(url)
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'ok')

    def test_botao_homologar_envia_por_formulario(self):
        livro = self._criar_livro('entregue')
        self.client.force_login(self.user_auditor)
        res = self.client.get(reverse('visualizar_controle_execucao', kwargs={'pk': livro.pk}))
        url_ok = reverse('alterar_status_execucao', kwargs={'pk': livro.pk, 'novo_status': 'ok'})
        self.assertContains(res, f'<form method="post" action="{url_ok}"')
        self.assertNotContains(res, f'href="{url_ok}"')

    # --- Extra: ?force=1 da Notificação restrito à ACI ---

    def test_force_notificacao_ignorado_para_anonimo(self):
        livro = self._criar_livro('rascunho')
        oc = OcorrenciaContratual.objects.create(controle=livro, descricao='Ocorrência notificada.', notificacao_emitida=True)
        url = reverse('download_notificacao_anexo_d_pdf', kwargs={'pk': oc.pk}) + '?force=1'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertNotEqual(res.get('Content-Type'), 'application/pdf')

    def test_force_notificacao_permitido_para_auditor(self):
        livro = self._criar_livro('rascunho')
        oc = OcorrenciaContratual.objects.create(controle=livro, descricao='Ocorrência notificada.', notificacao_emitida=True)
        self.client.force_login(self.user_auditor)
        url = reverse('download_notificacao_anexo_d_pdf', kwargs={'pk': oc.pk}) + '?force=1'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
