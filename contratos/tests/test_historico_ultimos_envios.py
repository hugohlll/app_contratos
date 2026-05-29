"""
Testes para a seção "Últimos Envios" da tela pública de detalhe do contrato.

Valida que a view detalhe_contrato retorna no máximo 6 prestações recentes,
ordenadas do mais recente para o mais antigo, excluindo status 'pendente',
e exibindo apenas o envio mais recente quando há múltiplos para o mesmo período.
"""
import os
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from contratos.models import (
    Contrato, Empresa, PrestacaoContas, Agente,
    PostoGraduacao, Comissao
)


class HistoricoUltimosEnviosTests(TestCase):
    """Suíte de testes para a seção Últimos Envios no acesso público."""

    def setUp(self):
        self.posto = PostoGraduacao.objects.create(
            sigla="CB", descricao="Cabo", senioridade=8
        )
        self.empresa = Empresa.objects.create(
            razao_social="Beta Serviços Ltda", cnpj="99888777000166"
        )
        self.agente = Agente.objects.create(
            nome_completo="Ana Oliveira", nome_de_guerra="Oliveira",
            posto=self.posto, saram="1112233"
        )
        self.contrato = Contrato.objects.create(
            numero="30/2026", objeto="Serviços Gerais",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=80000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO',
            ativa=True, data_inicio=date(2026, 1, 1)
        )
        self.url_detalhe = reverse(
            'detalhe_contrato', kwargs={'contrato_id': self.contrato.id}
        )
        self.client = Client()

    def _criar_prestacao(self, mes, ano, status='entregue'):
        """Helper para criar uma PrestacaoContas com arquivo PDF mínimo."""
        pdf = SimpleUploadedFile(
            f"pc_{mes}_{ano}.pdf", b"%PDF-1.4 test",
            content_type="application/pdf"
        )
        return PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=mes, ano_referencia=ano,
            arquivo=pdf, status=status
        )

    def tearDown(self):
        """Remove arquivos PDF gerados durante os testes."""
        for p in PrestacaoContas.objects.all():
            if p.arquivo:
                try:
                    if os.path.isfile(p.arquivo.path):
                        os.remove(p.arquivo.path)
                except (ValueError, FileNotFoundError):
                    pass

    # ---------------------------------------------------------------
    # 1. Limite de 6 registros
    # ---------------------------------------------------------------
    def test_limite_maximo_6_prestacoes(self):
        """A view deve retornar no máximo 6 prestações, mesmo existindo mais."""
        # Cria 8 prestações para meses consecutivos (jan a ago 2026)
        for mes in range(1, 9):
            self._criar_prestacao(mes, 2026)

        response = self.client.get(self.url_detalhe)
        self.assertEqual(response.status_code, 200)

        prestacoes = response.context['prestacoes_recentes']
        self.assertEqual(len(prestacoes), 6)

    # ---------------------------------------------------------------
    # 2. Ordenação decrescente (mais recente primeiro)
    # ---------------------------------------------------------------
    def test_ordenacao_decrescente_por_ano_mes(self):
        """As prestações devem ser ordenadas do período mais recente ao mais antigo."""
        self._criar_prestacao(1, 2026)
        self._criar_prestacao(3, 2026)
        self._criar_prestacao(5, 2026)

        response = self.client.get(self.url_detalhe)
        prestacoes = list(response.context['prestacoes_recentes'])

        periodos = [(p.mes_referencia, p.ano_referencia) for p in prestacoes]
        self.assertEqual(periodos, [(5, 2026), (3, 2026), (1, 2026)])

    # ---------------------------------------------------------------
    # 3. Período que cruza virada de ano
    # ---------------------------------------------------------------
    def test_ordenacao_cruzando_virada_de_ano(self):
        """Prestações de anos diferentes devem respeitar a ordenação ano > mês."""
        self._criar_prestacao(11, 2025)
        self._criar_prestacao(12, 2025)
        self._criar_prestacao(1, 2026)
        self._criar_prestacao(2, 2026)

        response = self.client.get(self.url_detalhe)
        prestacoes = list(response.context['prestacoes_recentes'])

        periodos = [(p.mes_referencia, p.ano_referencia) for p in prestacoes]
        self.assertEqual(periodos, [
            (2, 2026), (1, 2026), (12, 2025), (11, 2025)
        ])

    # ---------------------------------------------------------------
    # 4. Exclusão de status 'pendente'
    # ---------------------------------------------------------------
    def test_exclui_prestacoes_pendentes(self):
        """Prestações com status 'pendente' não devem aparecer nos últimos envios."""
        self._criar_prestacao(1, 2026, status='entregue')
        self._criar_prestacao(2, 2026, status='pendente')
        self._criar_prestacao(3, 2026, status='ok')

        response = self.client.get(self.url_detalhe)
        prestacoes = list(response.context['prestacoes_recentes'])

        meses = [p.mes_referencia for p in prestacoes]
        self.assertIn(1, meses)
        self.assertIn(3, meses)
        self.assertNotIn(2, meses)
        self.assertEqual(len(prestacoes), 2)

    # ---------------------------------------------------------------
    # 5. Deduplicação: múltiplos envios no mesmo período
    # ---------------------------------------------------------------
    def test_apenas_ultimo_envio_por_periodo(self):
        """Havendo múltiplos envios para o mesmo mês/ano, exibe apenas o mais recente (maior id)."""
        p1 = self._criar_prestacao(5, 2026)
        p2 = self._criar_prestacao(5, 2026)  # reenvio — id maior

        response = self.client.get(self.url_detalhe)
        prestacoes = list(response.context['prestacoes_recentes'])

        self.assertEqual(len(prestacoes), 1)
        self.assertEqual(prestacoes[0].id, p2.id)

    # ---------------------------------------------------------------
    # 6. Prioridade do limite: exibe os 6 mais recentes
    # ---------------------------------------------------------------
    def test_limite_6_descarta_os_mais_antigos(self):
        """Com mais de 6 períodos, os mais antigos devem ser descartados."""
        # Cria jan a ago (8 meses)
        for mes in range(1, 9):
            self._criar_prestacao(mes, 2026)

        response = self.client.get(self.url_detalhe)
        prestacoes = list(response.context['prestacoes_recentes'])

        meses = [p.mes_referencia for p in prestacoes]
        # Deve conter ago(8) a mar(3), excluindo jan(1) e fev(2)
        self.assertEqual(meses, [8, 7, 6, 5, 4, 3])
        self.assertNotIn(1, meses)
        self.assertNotIn(2, meses)

    # ---------------------------------------------------------------
    # 7. Sem envios: contexto vazio
    # ---------------------------------------------------------------
    def test_nenhum_envio_retorna_lista_vazia(self):
        """Sem prestações cadastradas, o contexto deve conter lista vazia e exibir mensagem adequada."""
        response = self.client.get(self.url_detalhe)
        self.assertEqual(response.status_code, 200)

        prestacoes = response.context['prestacoes_recentes']
        self.assertEqual(len(prestacoes), 0)
        self.assertContains(response, "Nenhum envio registrado")

    # ---------------------------------------------------------------
    # 8. Todos os status válidos aparecem
    # ---------------------------------------------------------------
    def test_todos_status_validos_aparecem(self):
        """Prestações com status 'entregue', 'correcao' e 'ok' devem todas aparecer."""
        self._criar_prestacao(1, 2026, status='entregue')
        self._criar_prestacao(2, 2026, status='correcao')
        self._criar_prestacao(3, 2026, status='ok')

        response = self.client.get(self.url_detalhe)
        prestacoes = list(response.context['prestacoes_recentes'])

        status_list = [p.status for p in prestacoes]
        self.assertIn('entregue', status_list)
        self.assertIn('correcao', status_list)
        self.assertIn('ok', status_list)
        self.assertEqual(len(prestacoes), 3)

    # ---------------------------------------------------------------
    # 9. Referência mes/ano renderizada corretamente no HTML
    # ---------------------------------------------------------------
    def test_referencia_renderizada_no_html(self):
        """O badge de referência deve exibir o formato MM/AAAA correto no HTML."""
        self._criar_prestacao(3, 2026)
        self._criar_prestacao(11, 2025)

        response = self.client.get(self.url_detalhe)
        self.assertContains(response, "03/2026")
        self.assertContains(response, "11/2025")
        # Não deve conter formato com ponto de milhar (ex: 2.026)
        self.assertNotContains(response, "2.026")
        self.assertNotContains(response, "2.025")

    # ---------------------------------------------------------------
    # 10. Isolamento entre contratos
    # ---------------------------------------------------------------
    def test_isolamento_entre_contratos(self):
        """Prestações de outro contrato não devem aparecer nos últimos envios."""
        outro_contrato = Contrato.objects.create(
            numero="99/2026", objeto="Outro Serviço",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=10000.00
        )
        Comissao.objects.create(
            contrato=outro_contrato, tipo='FISCALIZACAO',
            ativa=True, data_inicio=date(2026, 1, 1)
        )

        # Prestação no contrato alvo
        self._criar_prestacao(5, 2026)

        # Prestação em outro contrato
        pdf = SimpleUploadedFile("outro.pdf", b"%PDF-1.4", content_type="application/pdf")
        PrestacaoContas.objects.create(
            contrato=outro_contrato, agente=self.agente,
            mes_referencia=5, ano_referencia=2026,
            arquivo=pdf, status='entregue'
        )

        response = self.client.get(self.url_detalhe)
        prestacoes = list(response.context['prestacoes_recentes'])

        self.assertEqual(len(prestacoes), 1)
        self.assertEqual(prestacoes[0].contrato, self.contrato)
