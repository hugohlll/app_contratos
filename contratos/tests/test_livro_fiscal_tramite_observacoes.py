"""
Testes para separação das observações do Livro do Fiscal e observações de trâmite com a ACI.
"""
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from contratos.models import (
    Contrato, Empresa, Agente, PostoGraduacao, ControleExecucao,
    HistoricoObservacaoExecucao, Comissao, Integrante, Funcao
)


class LivroFiscalTramiteObservacoesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin_test', 'admin@example.com', 'pass123')
        self.client.force_login(self.user)

        self.posto = PostoGraduacao.objects.create(sigla="Cap", descricao="Capitão", senioridade=3)
        self.agente = Agente.objects.create(
            nome_completo="Fiscal Responsavel Teste",
            nome_de_guerra="Responsavel",
            posto=self.posto,
            saram="998877",
            cpf="111.222.333-44"
        )
        self.empresa = Empresa.objects.create(razao_social="Empresa Prestadora", cnpj="11.222.333/0001-44")
        self.contrato = Contrato.objects.create(
            numero="100/2026",
            objeto="Serviços Gerais",
            tipo="DESPESA",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=50000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO', ativa=True, data_inicio=date(2026, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal Titular", sigla="FT")
        Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date(2026, 1, 1), portaria_numero="100", portaria_data=date(2026, 1, 1)
        )

        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        self.mes_ref = mes_anterior.month
        self.ano_ref = mes_anterior.year

        self.url_formulario = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id}) + f"?mes={self.mes_ref}&ano={self.ano_ref}"
        self.url_prestacao = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})

    def test_modal_confirmacao_presente_no_formulario(self):
        """Verifica se o modal de confirmação e o campo de observação de trâmite são renderizados no formulário."""
        res = self.client.get(self.url_formulario)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="modalConfirmarFinalizacao"')
        self.assertContains(res, 'name="observacao_tramite"')
        self.assertContains(res, 'Observações para a ACI (Opcional)')

    def test_finalizar_com_observacao_tramite_registra_historico_separado(self):
        """Ao finalizar com observação de trâmite, esta é salva em HistoricoObservacaoExecucao e não duplica observações do livro."""
        data = {
            'agente': self.agente.id,
            'mes_referencia': self.mes_ref,
            'ano_referencia': self.ano_ref,
            'status': 'entregue',
            'sem_ocorrencias_periodo': 'on',
            'observacao': 'Nada mais a declarar no Livro',
            'observacao_tramite': 'Esclarecimento enviado à ACI durante o trâmite',
            'acao': 'finalizar',
        }
        res = self.client.post(self.url_formulario, data)
        self.assertEqual(res.status_code, 302)

        ctrl = ControleExecucao.objects.filter(
            contrato=self.contrato, mes_referencia=self.mes_ref, ano_referencia=self.ano_ref
        ).first()
        self.assertIsNotNone(ctrl)
        self.assertEqual(ctrl.status, 'entregue')
        self.assertEqual(ctrl.observacao, 'Nada mais a declarar no Livro')

        # Apenas 1 registro no histórico com a observação de trâmite
        historico = ctrl.historico_observacoes.all()
        self.assertEqual(historico.count(), 1)
        self.assertEqual(historico.first().observacao, 'Esclarecimento enviado à ACI durante o trâmite')

        # Na tela de prestação, apenas a observação de trâmite aparece na caixa de trâmites
        res_prestacao = self.client.get(self.url_prestacao)
        self.assertEqual(res_prestacao.status_code, 200)
        self.assertContains(res_prestacao, 'Esclarecimento enviado à ACI durante o trâmite')
        self.assertNotContains(res_prestacao, 'Nada mais a declarar no Livro')

    def test_finalizar_sem_observacao_tramite_nao_cria_historico(self):
        """Ao finalizar sem preencher observação de trâmite, nenhum histórico é criado e o livro mantém sua observação."""
        data = {
            'agente': self.agente.id,
            'mes_referencia': self.mes_ref,
            'ano_referencia': self.ano_ref,
            'status': 'entregue',
            'sem_ocorrencias_periodo': 'on',
            'observacao': 'Nada mais a declarar no Livro',
            'observacao_tramite': '',
            'acao': 'finalizar',
        }
        res = self.client.post(self.url_formulario, data)
        self.assertEqual(res.status_code, 302)

        ctrl = ControleExecucao.objects.filter(
            contrato=self.contrato, mes_referencia=self.mes_ref, ano_referencia=self.ano_ref
        ).first()
        self.assertIsNotNone(ctrl)
        self.assertEqual(ctrl.status, 'entregue')
        self.assertEqual(ctrl.observacao, 'Nada mais a declarar no Livro')

        # Nenhum histórico criado
        self.assertEqual(ctrl.historico_observacoes.count(), 0)

        # Na tela de prestação, não há fallback para a observação do livro
        res_prestacao = self.client.get(self.url_prestacao)
        self.assertEqual(res_prestacao.status_code, 200)
        self.assertNotContains(res_prestacao, 'Nada mais a declarar no Livro')

    def test_salvar_rascunho_nao_registra_historico_tramite(self):
        """Ao salvar como rascunho, o histórico de trâmites não deve ser criado mesmo se observacao_tramite for passada."""
        data = {
            'agente': self.agente.id,
            'mes_referencia': self.mes_ref,
            'ano_referencia': self.ano_ref,
            'status': 'rascunho',
            'sem_ocorrencias_periodo': 'on',
            'observacao': 'Texto de rascunho',
            'observacao_tramite': 'Tentativa de mensagem em rascunho',
            'acao': 'rascunho',
        }
        res = self.client.post(self.url_formulario, data)
        self.assertEqual(res.status_code, 302)

        ctrl = ControleExecucao.objects.filter(
            contrato=self.contrato, mes_referencia=self.mes_ref, ano_referencia=self.ano_ref
        ).first()
        self.assertIsNotNone(ctrl)
        self.assertEqual(ctrl.status, 'rascunho')
        self.assertEqual(ctrl.historico_observacoes.count(), 0)
