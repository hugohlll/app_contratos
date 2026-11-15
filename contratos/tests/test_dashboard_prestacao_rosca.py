"""Testes da rosca alternável do painel de Prestação de Contas (contagens e filtro da tabela)."""
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

import json

from contratos.models import (
    Agente, Contrato, ControleExecucao, Empresa, PostoGraduacao, PrestacaoContas,
    PrestacaoContasSetor, Setor,
)
from contratos.views.prestacao import (
    CHAVES_ROSCA, CHAVES_ROSCA_SETORES, _get_dashboard_stats, status_grafico,
)

# Mesmas chaves que o prestacao-rosca.js lê para cada visão.
VISOES = {
    'todos': ('ok_no_mes', 'entregues_no_mes', 'correcao_no_mes', 'pendentes_no_mes'),
    'prioritarios': ('prio_ok', 'prio_entregues', 'prio_correcao', 'prio_pendentes'),
    'livro': ('livro_ok', 'livro_entregues', 'livro_correcao', 'livro_pendentes'),
}
VISOES_SETORES = {
    'todos': ('ok_setores_no_mes', 'entregues_setores_no_mes', 'correcao_setores_no_mes', 'pendentes_setores_no_mes'),
    'prioritarios': ('prio_ok_setores', 'prio_entregues_setores', 'prio_correcao_setores', 'prio_pendentes_setores'),
}
STATUS = ('ok', 'entregue', 'correcao', 'pendente')


def linha_passa(item, visao, status):
    """Reproduz RoscaPrestacao.linhaPassa (prestacao-rosca.js) sobre uma linha da tabela do mês."""
    if visao == 'livro':
        return item['segmento_livro'] == status
    if visao == 'prioritarios' and not item['prioritario']:
        return False
    return item['segmento_slides'] == status


class StatusGraficoTest(TestCase):
    def test_agrupa_status_fora_do_grafico_em_pendente(self):
        for status in ('ok', 'entregue', 'correcao'):
            self.assertEqual(status_grafico(status), status)
        for status in ('pendente', 'rascunho', None, ''):
            self.assertEqual(status_grafico(status), 'pendente')


class RoscaPrestacaoTest(TestCase):
    def setUp(self):
        hoje = date.today()
        anterior = hoje.replace(day=1) - timedelta(days=1)
        self.mes, self.ano = anterior.month, anterior.year

        self.user = User.objects.create_superuser('admin_rosca', 'admin@rosca.test', 'senha-teste-123')
        self.user.groups.add(Group.objects.get_or_create(name='Auditores')[0])
        self.client.force_login(self.user)

        posto = PostoGraduacao.objects.create(descricao='Major', sigla='Maj', senioridade=1)
        self.agente = Agente.objects.create(nome_completo='Ana Rosca', nome_de_guerra='Ana', posto=posto, saram='9001')
        empresa = Empresa.objects.create(razao_social='Empresa Rosca', cnpj='11.222.333/0001-44')

        def contrato(numero):
            return Contrato.objects.create(
                numero=numero, objeto='Objeto', empresa=empresa, valor_total=1000,
                vigencia_inicio=hoje - timedelta(days=200), vigencia_fim=hoje + timedelta(days=200))

        # slides: ok prioritário, entregue prioritário, correção, pendente explícito, sem entrega
        self.c_ok = contrato('R01/2026')
        self.c_entregue = contrato('R02/2026')
        self.c_correcao = contrato('R03/2026')
        self.c_pendente = contrato('R04/2026')
        self.c_sem = contrato('R05/2026')
        self._prestacao(self.c_ok, 'ok', prioritario=True)
        self._prestacao(self.c_entregue, 'entregue', prioritario=True)
        self._prestacao(self.c_correcao, 'correcao')
        self._prestacao(self.c_pendente, 'pendente', prioritario=True)

        # livro: ok, correção, rascunho (conta como pendente), demais sem registro
        self._livro(self.c_ok, 'ok')
        self._livro(self.c_correcao, 'correcao')
        self._livro(self.c_sem, 'rascunho')

    def _prestacao(self, contrato, status, prioritario=False):
        return PrestacaoContas.objects.create(
            contrato=contrato, mes_referencia=self.mes, ano_referencia=self.ano,
            status=status, agente=self.agente, compor_apresentacao=prioritario)

    def _livro(self, contrato, status):
        return ControleExecucao.objects.create(
            contrato=contrato, mes_referencia=self.mes, ano_referencia=self.ano,
            agente=self.agente, status=status)

    def _painel(self):
        return self.client.get(reverse('dashboard_prestacao'), {'mes': self.mes, 'ano': self.ano})

    def test_contagens_das_tres_visoes(self):
        stats = _get_dashboard_stats(self.ano, self.mes)
        self.assertEqual([stats[k] for k in VISOES['todos']], [1, 1, 1, 2])
        self.assertEqual([stats[k] for k in VISOES['prioritarios']], [1, 1, 0, 1])
        self.assertEqual([stats[k] for k in VISOES['livro']], [1, 0, 1, 3])

    def test_contagem_da_rosca_igual_as_linhas_filtradas(self):
        resp = self._painel()
        stats = resp.context['rosca_stats']
        linhas = resp.context['entregas_mes_selecionado']
        for visao, chaves in VISOES.items():
            for status, chave in zip(STATUS, chaves):
                filtradas = [i for i in linhas if linha_passa(i, visao, status)]
                self.assertEqual(len(filtradas), stats[chave], f'{visao}:{status}')

    def test_painel_entrega_dados_da_rosca(self):
        resp = self._painel()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.context['rosca_stats']), set(CHAVES_ROSCA))
        self.assertContains(resp, 'id="roscaStatsDados"')
        self.assertContains(resp, 'prestacao-rosca.js')
        self.assertContains(resp, 'chart.js@4.4.0')
        self.assertContains(resp, 'data-rosca-visao="livro"')
        self.assertNotContains(resp, 'prestacoesPieChart')
        self.assertNotContains(resp, 'prioritariosBarChart')

    def test_linhas_trazem_segmentos_para_o_filtro(self):
        resp = self._painel()
        self.assertContains(
            resp, 'data-segmento-slides="ok" data-segmento-livro="ok" data-prioritario="1"')
        self.assertContains(
            resp, 'data-segmento-slides="pendente" data-segmento-livro="pendente" data-prioritario="0"')

    def test_livro_em_rascunho_nao_aparece_como_entregue(self):
        resp = self._painel()
        self.assertContains(resp, 'Em andamento')
        linha = next(i for i in resp.context['entregas_mes_selecionado'] if i['contrato'] == self.c_sem)
        self.assertEqual(linha['segmento_livro'], 'pendente')

    def test_ajax_de_status_devolve_contagens_da_rosca(self):
        prestacao = PrestacaoContas.objects.get(contrato=self.c_entregue)
        resp = self.client.get(
            reverse('alterar_status_prestacao', args=[prestacao.id, 'ok']),
            {'ajax': '1', 'mes': self.mes, 'ano': self.ano},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()['stats']
        for chave in CHAVES_ROSCA:
            self.assertIn(chave, stats)
        self.assertEqual(stats['ok_no_mes'], 2)
        self.assertEqual(stats['prio_ok'], 2)


class RoscaSetoresTest(TestCase):
    """Rosca da aba Setores: Todos e Prioritários no mesmo quadro."""

    def setUp(self):
        anterior = date.today().replace(day=1) - timedelta(days=1)
        self.mes, self.ano = anterior.month, anterior.year

        self.user = User.objects.create_superuser('admin_setores', 'admin@setores.test', 'senha-teste-123')
        self.user.groups.add(Group.objects.get_or_create(name='Auditores')[0])
        self.client.force_login(self.user)

        self.s_ok = Setor.objects.create(nome='Setor OK', sigla='SOK')
        self.s_entregue = Setor.objects.create(nome='Setor Entregue', sigla='SEN')
        self.s_correcao = Setor.objects.create(nome='Setor Correção', sigla='SCO')
        self.s_pendente = Setor.objects.create(nome='Setor Pendente', sigla='SPE')
        self.s_sem = Setor.objects.create(nome='Setor Sem Entrega', sigla='SSE')
        self._prestacao(self.s_ok, 'ok', prioritario=True)
        self._prestacao(self.s_entregue, 'entregue')
        self._prestacao(self.s_correcao, 'correcao', prioritario=True)
        self._prestacao(self.s_pendente, 'pendente', prioritario=True)

    def _prestacao(self, setor, status, prioritario=False):
        return PrestacaoContasSetor.objects.create(
            setor=setor, mes_referencia=self.mes, ano_referencia=self.ano,
            status=status, compor_apresentacao=prioritario)

    def _painel(self):
        return self.client.get(reverse('dashboard_prestacao'), {'mes': self.mes, 'ano': self.ano, 'tab': 'setores'})

    def test_contagens_das_duas_visoes(self):
        stats = _get_dashboard_stats(self.ano, self.mes)
        self.assertEqual([stats[k] for k in VISOES_SETORES['todos']], [1, 1, 1, 2])
        self.assertEqual([stats[k] for k in VISOES_SETORES['prioritarios']], [1, 0, 1, 1])

    def test_contagem_da_rosca_igual_as_linhas_filtradas(self):
        resp = self._painel()
        stats = resp.context['rosca_setores_stats']
        linhas = resp.context['entregas_setor_mes_selecionado']
        for visao, chaves in VISOES_SETORES.items():
            for status, chave in zip(STATUS, chaves):
                filtradas = [i for i in linhas if linha_passa(i, visao, status)]
                self.assertEqual(len(filtradas), stats[chave], f'{visao}:{status}')

    def test_painel_entrega_rosca_de_setores(self):
        resp = self._painel()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.context['rosca_setores_stats']), set(CHAVES_ROSCA_SETORES))
        self.assertContains(resp, 'id="roscaSetoresDados"')
        self.assertContains(resp, 'id="cardRoscaSetores"')
        self.assertContains(resp, 'id="filtroGraficoSetoresAtivo"')
        self.assertNotContains(resp, 'prioritariosSetoresBarChart')
        self.assertContains(resp, 'data-segmento-slides="ok" data-prioritario="1"')
        self.assertContains(resp, 'data-segmento-slides="pendente" data-prioritario="0"')

    def test_toggle_prioritario_devolve_contagens_da_rosca(self):
        resp = self.client.post(
            reverse('toggle_apresentacao_prestacao_setor'),
            data=json.dumps({
                'checked': True, 'setor_id': self.s_entregue.id, 'mes': self.mes, 'ano': self.ano,
                'dashboard_mes': self.mes, 'dashboard_ano': self.ano,
            }),
            content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()['stats']
        for chave in CHAVES_ROSCA_SETORES:
            self.assertIn(chave, stats)
        self.assertEqual(stats['prio_entregues_setores'], 1)
