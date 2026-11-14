"""
Testes da conformidade automática do Livro do Fiscal: o ateste sem ocorrências, dentro do prazo
e de Livro nunca devolvido vai direto para 'ok', sem análise da ACI.
"""
import csv
import io
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contratos.models import (
    ApontamentoCorrecaoExecucao, CalendarioPrestacao, Comissao, Contrato, ControleExecucao,
    Agente, Empresa, Funcao, HistoricoObservacaoExecucao, Integrante, OcorrenciaContratual,
    PostoGraduacao,
)
from contratos.services.ocorrencias import OcorrenciasService


class ConformidadeAutomaticaBase(TestCase):
    def setUp(self):
        self.client = Client()
        self.group_auditor = Group.objects.create(name='Auditores')
        self.user_auditor = User.objects.create_user(username='auditor_conf', password='pwd123')
        self.user_auditor.groups.add(self.group_auditor)

        self.posto = PostoGraduacao.objects.create(sigla="Cap", descricao="Capitão", senioridade=3)
        self.agente = Agente.objects.create(
            nome_completo="Fiscal Conformidade", nome_de_guerra="Conformidade", posto=self.posto, saram="445566"
        )
        self.empresa = Empresa.objects.create(razao_social="Empresa Conformidade", cnpj="33.444.555/0001-66")
        self.contrato = Contrato.objects.create(
            numero="300/2026", objeto="Serviços de Limpeza", tipo="DESPESA", empresa=self.empresa,
            vigencia_inicio=date.today() - timedelta(days=365), vigencia_fim=date.today() + timedelta(days=365), valor_total=90000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO', ativa=True, data_inicio=date(2026, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal Titular", sigla="FT")
        Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date(2026, 1, 1), portaria_numero="300", portaria_data=date(2026, 1, 1)
        )

        self.hoje = timezone.localdate()
        mes_anterior = self.hoje.replace(day=1) - timedelta(days=1)
        self.mes, self.ano = mes_anterior.month, mes_anterior.year
        self.url_formulario = (
            reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
            + f"?mes={self.mes}&ano={self.ano}"
        )
        self.url_prestacao = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})

    def _calendario(self, data_limite):
        return CalendarioPrestacao.objects.create(mes=self.mes, ano=self.ano, data_entrega_execucao=data_limite)

    def _criar_livro(self, status='rascunho', **kwargs):
        return ControleExecucao.objects.create(
            contrato=self.contrato, agente=self.agente, mes_referencia=self.mes, ano_referencia=self.ano,
            status=status, **kwargs
        )

    def _devolver(self, livro):
        livro.status = 'correcao'
        livro.save()
        return ApontamentoCorrecaoExecucao.objects.create(
            controle=livro, autor=self.user_auditor, descricao='Corrigir o período informado.'
        )

    def _payload(self, sem_ocorrencias=True, acao='finalizar', mes=None, ano=None, **extras):
        data = {
            'agente': self.agente.id,
            'mes_referencia': mes or self.mes,
            'ano_referencia': ano or self.ano,
            'status': 'rascunho',
            'omap': 'GAP-BR',
            'unidade_gestora': '120006 - GAP-BR',
            'acao': acao,
        }
        if sem_ocorrencias:
            data['sem_ocorrencias_periodo'] = 'on'
        data.update(extras)
        return data

    def _finalizar(self, **kwargs):
        res = self.client.post(self.url_formulario, self._payload(**kwargs))
        self.assertEqual(res.status_code, 302)
        return ControleExecucao.objects.get(
            contrato=self.contrato, mes_referencia=self.mes, ano_referencia=self.ano
        ), res

    def assertAutomatico(self, livro):
        self.assertEqual(livro.status, 'ok')
        self.assertTrue(livro.conformidade_automatica)

    def assertFilaDaACI(self, livro):
        self.assertEqual(livro.status, 'entregue')
        self.assertFalse(livro.conformidade_automatica)


class ElegibilidadeTests(ConformidadeAutomaticaBase):
    def test_dentro_do_prazo_vai_para_ok(self):
        self._calendario(self.hoje + timedelta(days=3))
        livro, _ = self._finalizar()
        self.assertAutomatico(livro)

    def test_exatamente_no_dia_limite_vai_para_ok(self):
        self._calendario(self.hoje)
        livro, _ = self._finalizar()
        self.assertAutomatico(livro)

    def test_sem_calendario_conta_como_dentro_do_prazo(self):
        livro, _ = self._finalizar()
        self.assertAutomatico(livro)

    def test_calendario_sem_data_conta_como_dentro_do_prazo(self):
        self._calendario(None)
        livro, _ = self._finalizar()
        self.assertAutomatico(livro)

    def test_atrasado_vai_para_entregue(self):
        self._calendario(self.hoje - timedelta(days=1))
        livro, _ = self._finalizar()
        self.assertFilaDaACI(livro)

    def test_flag_com_ocorrencias_e_recusada(self):
        livro = self._criar_livro()
        OcorrenciaContratual.objects.create(controle=livro, descricao='Atraso na entrega do material.')
        res = self.client.post(self.url_formulario, self._payload(), follow=True)
        self.assertContains(res, 'Existem 1 ocorrência(s) registrada(s) neste mês.')
        livro.refresh_from_db()
        self.assertEqual(livro.status, 'rascunho')
        self.assertFalse(livro.conformidade_automatica)

    def test_ocorrencias_sem_flag_seguem_para_entregue(self):
        livro = self._criar_livro()
        OcorrenciaContratual.objects.create(controle=livro, descricao='Atraso na entrega do material.')
        livro, _ = self._finalizar(sem_ocorrencias=False)
        self.assertFilaDaACI(livro)

    def test_livro_devolvido_reatestado_vai_para_entregue(self):
        self._devolver(self._criar_livro())
        livro, _ = self._finalizar()
        self.assertFilaDaACI(livro)

    def test_livro_devolvido_salvo_como_rascunho_nao_escapa_da_aci(self):
        self._devolver(self._criar_livro())
        livro, _ = self._finalizar(acao='rascunho')
        self.assertEqual(livro.status, 'rascunho')
        livro, _ = self._finalizar()
        self.assertFilaDaACI(livro)

    def test_livro_em_correcao_sem_apontamento_nao_escapa_da_aci(self):
        self._criar_livro('correcao')
        livro, _ = self._finalizar()
        self.assertFilaDaACI(livro)

    def test_exclusao_publica_nao_apaga_registro_de_devolucao(self):
        url = reverse('excluir_controle_execucao_publico', kwargs={'contrato_id': self.contrato.id})

        livro = self._criar_livro()
        self._devolver(livro)
        self.client.post(url)
        self.assertTrue(ControleExecucao.objects.filter(pk=livro.pk).exists())

        livro.status = 'rascunho'
        livro.save()
        self.client.post(url)
        self.assertTrue(ControleExecucao.objects.filter(pk=livro.pk).exists())
        self.assertEqual(livro.apontamentos.count(), 1)

    def test_rascunho_nao_recebe_a_marca(self):
        livro, _ = self._finalizar(acao='rascunho')
        self.assertEqual(livro.status, 'rascunho')
        self.assertFalse(livro.conformidade_automatica)

    def test_mes_corrente_continua_rascunho(self):
        url = (
            reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
            + f"?mes={self.hoje.month}&ano={self.hoje.year}"
        )
        res = self.client.post(url, self._payload(mes=self.hoje.month, ano=self.hoje.year))
        self.assertEqual(res.status_code, 302)
        livro = ControleExecucao.objects.get(
            contrato=self.contrato, mes_referencia=self.hoje.month, ano_referencia=self.hoje.year
        )
        self.assertEqual(livro.status, 'rascunho')
        self.assertFalse(livro.conformidade_automatica)

    def test_entregue_preexistente_nao_muda(self):
        livro = self._criar_livro('entregue', sem_ocorrencias_periodo=True)
        res = self.client.post(self.url_formulario, self._payload())
        self.assertEqual(res.status_code, 302)
        livro.refresh_from_db()
        self.assertFilaDaACI(livro)

    def test_servico_exige_a_declaracao_de_sem_ocorrencias(self):
        self.assertFalse(OcorrenciasService.conformidade_automatica_aplicavel(None, False, self.mes, self.ano))
        self.assertTrue(OcorrenciasService.conformidade_automatica_aplicavel(None, True, self.mes, self.ano))

    def test_mensagem_de_sucesso_propria(self):
        _, res = self._finalizar()
        self.assertRedirects(res, self.url_prestacao, fetch_redirect_response=False)
        textos = [str(m) for m in get_messages(res.wsgi_request)]
        self.assertTrue(any('conformidade automática' in t and 'PDF' in t for t in textos), textos)

    def test_mensagem_de_sucesso_comum_quando_vai_para_a_aci(self):
        self._calendario(self.hoje - timedelta(days=1))
        _, res = self._finalizar()
        textos = [str(m) for m in get_messages(res.wsgi_request)]
        self.assertTrue(any('finalizado e atestado com sucesso' in t for t in textos), textos)


class TramiteTests(ConformidadeAutomaticaBase):
    def test_observacao_tramite_ignorada_no_automatico(self):
        livro, _ = self._finalizar(observacao='Consta no PDF', observacao_tramite='Mensagem para a ACI')
        self.assertAutomatico(livro)
        self.assertEqual(livro.observacao, 'Consta no PDF')
        self.assertFalse(HistoricoObservacaoExecucao.objects.filter(controle=livro).exists())

    def test_observacao_tramite_registrada_quando_vai_para_a_aci(self):
        self._calendario(self.hoje - timedelta(days=1))
        livro, _ = self._finalizar(observacao_tramite='Mensagem para a ACI')
        self.assertFilaDaACI(livro)
        self.assertEqual(livro.historico_observacoes.get().observacao, 'Mensagem para a ACI')


class AcoesDaACITests(ConformidadeAutomaticaBase):
    def _alterar_status(self, livro, novo_status, **data):
        self.client.force_login(self.user_auditor)
        url = reverse('alterar_status_execucao', kwargs={'pk': livro.pk, 'novo_status': novo_status})
        self.assertEqual(self.client.post(url, data).status_code, 302)
        livro.refresh_from_db()

    def test_devolucao_zera_a_marca_e_reateste_vai_para_a_aci(self):
        livro, _ = self._finalizar()
        self._alterar_status(livro, 'correcao', justificativa='Revisar a declaração.')
        self.assertEqual(livro.status, 'correcao')
        self.assertFalse(livro.conformidade_automatica)

        self.client.logout()
        livro, _ = self._finalizar()
        self.assertFilaDaACI(livro)

    def test_homologacao_manual_zera_a_marca(self):
        livro = self._criar_livro('ok', conformidade_automatica=True)
        self._alterar_status(livro, 'ok')
        self.assertEqual(livro.status, 'ok')
        self.assertFalse(livro.conformidade_automatica)

    def test_homologacao_de_entregue_nao_marca_automatica(self):
        livro = self._criar_livro('entregue')
        self._alterar_status(livro, 'ok')
        self.assertEqual(livro.status, 'ok')
        self.assertFalse(livro.conformidade_automatica)

    def test_csv_tem_coluna_de_conformidade_automatica(self):
        self._criar_livro('ok', conformidade_automatica=True)
        outro = Contrato.objects.create(
            numero="301/2026", objeto="Outro", tipo="DESPESA", empresa=self.empresa,
            vigencia_inicio=date.today() - timedelta(days=365), vigencia_fim=date.today() + timedelta(days=365), valor_total=1000.00
        )
        ControleExecucao.objects.create(
            contrato=outro, agente=self.agente, mes_referencia=self.mes, ano_referencia=self.ano, status='ok'
        )
        self.client.force_login(self.user_auditor)
        res = self.client.get(reverse('exportar_execucao_csv') + f"?mes={self.mes}&ano={self.ano}")
        self.assertEqual(res.status_code, 200)
        linhas = list(csv.DictReader(io.StringIO(res.content.decode('utf-8-sig')), delimiter=';'))
        valores = {linha['Contrato']: linha['Conformidade Automática?'] for linha in linhas}
        self.assertEqual(valores, {'300/2026': 'Sim', '301/2026': 'Não'})


class AcessoAoLivroOkTests(ConformidadeAutomaticaBase):
    def test_anonimo_baixa_o_pdf_logo_apos_o_ateste(self):
        livro, _ = self._finalizar()
        res = self.client.get(reverse('download_livro_fiscal_pdf', kwargs={'pk': livro.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(b''.join(res.streaming_content).startswith(b'%PDF'))

    def test_anonimo_nao_baixa_o_pdf_quando_vai_para_a_aci(self):
        self._calendario(self.hoje - timedelta(days=1))
        livro, _ = self._finalizar()
        res = self.client.get(reverse('download_livro_fiscal_pdf', kwargs={'pk': livro.pk}))
        self.assertEqual(res.status_code, 302)

    def test_anonimo_redirecionado_para_prestacao_do_mesmo_periodo(self):
        livro = self._criar_livro('ok', conformidade_automatica=True)
        res = self.client.get(self.url_formulario)
        self.assertRedirects(
            res, f"{self.url_prestacao}?mes={self.mes}&ano={self.ano}", fetch_redirect_response=False
        )
        destino = self.client.get(res.url)
        self.assertEqual(destino.status_code, 200)
        self.assertEqual(destino.context['controle_execucao'], livro)

    def test_autenticado_redirecionado_para_visualizacao(self):
        livro = self._criar_livro('ok')
        self.client.force_login(self.user_auditor)
        res = self.client.get(self.url_formulario)
        self.assertRedirects(
            res, reverse('visualizar_controle_execucao', kwargs={'pk': livro.pk}), fetch_redirect_response=False
        )


class TelasTests(ConformidadeAutomaticaBase):
    def test_formulario_elegivel_prepara_ocultacao_do_campo(self):
        res = self.client.get(self.url_formulario)
        self.assertTrue(res.context['conformidade_automatica_elegivel'])
        self.assertContains(res, 'const conformidadeAutomaticaElegivel = true;')
        self.assertContains(res, 'id="containerObservacaoTramite"')
        self.assertContains(res, 'id="avisoConformidadeAutomatica"')
        self.assertContains(res, 'sem análise da ACI')
        self.assertContains(res, "$('#id_observacao_tramite').val('');")

    def test_formulario_fora_do_prazo_nao_e_elegivel(self):
        self._calendario(self.hoje - timedelta(days=1))
        res = self.client.get(self.url_formulario)
        self.assertFalse(res.context['conformidade_automatica_elegivel'])
        self.assertContains(res, 'const conformidadeAutomaticaElegivel = false;')
        self.assertNotContains(res, 'id="avisoConformidadeAutomatica"')
        self.assertContains(res, 'name="observacao_tramite"')

    def test_formulario_de_livro_devolvido_nao_e_elegivel(self):
        livro = self._criar_livro()
        self._devolver(livro)
        res = self.client.get(self.url_formulario)
        self.assertFalse(res.context['conformidade_automatica_elegivel'])

    def test_formulario_do_mes_corrente_nao_e_elegivel(self):
        url = (
            reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
            + f"?mes={self.hoje.month}&ano={self.hoje.year}"
        )
        res = self.client.get(url)
        self.assertFalse(res.context['conformidade_automatica_elegivel'])

    def test_tooltip_do_pdf_nao_depende_apenas_da_aci(self):
        self._criar_livro('rascunho')
        res = self.client.get(self.url_formulario)
        self.assertNotContains(res, 'Download disponível apenas após conformidade da ACI')

    def test_prestacao_automatica_nao_afirma_analise(self):
        self._criar_livro('ok', conformidade_automatica=True)
        res = self.client.get(self.url_prestacao)
        self.assertContains(res, 'Conformidade automática: livro sem ocorrências')
        self.assertNotContains(res, 'analisado e aprovado')
        self.assertContains(res, 'Insira o documento gerado no SILOMS')
        self.assertContains(res, 'Baixar Livro do Fiscal (PDF)')

    def test_prestacao_homologada_mantem_texto_de_analise(self):
        self._criar_livro('ok')
        res = self.client.get(self.url_prestacao)
        self.assertContains(res, 'analisado e aprovado')
        self.assertNotContains(res, 'Conformidade automática: livro sem ocorrências')

    def test_visualizacao_indica_automatica_e_mantem_solicitar_correcao(self):
        livro = self._criar_livro('ok', conformidade_automatica=True)
        self.client.force_login(self.user_auditor)
        res = self.client.get(reverse('visualizar_controle_execucao', kwargs={'pk': livro.pk}))
        self.assertContains(res, 'Conformidade (OK!) — Automática')
        self.assertContains(res, 'Solicitar Correção')

    def test_visualizacao_homologada_nao_indica_automatica(self):
        livro = self._criar_livro('ok')
        self.client.force_login(self.user_auditor)
        res = self.client.get(reverse('visualizar_controle_execucao', kwargs={'pk': livro.pk}))
        self.assertNotContains(res, '— Automática')
