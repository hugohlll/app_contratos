"""Testes do drill-down do Painel de Auditoria (serviço de indicadores e endpoint de detalhe)."""
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from contratos.models import (
    Agente, Comissao, Contrato, Empresa, Funcao, Integrante, PostoGraduacao,
    DIAS_VALIDADE_QUALIFICACAO,
)
from contratos.services import indicadores


class ClassificacaoTest(TestCase):
    def test_limites_vencimento_comissao(self):
        self.assertEqual(indicadores.classificar_vencimento_comissao(0), 'critico')
        self.assertEqual(indicadores.classificar_vencimento_comissao(7), 'critico')
        self.assertEqual(indicadores.classificar_vencimento_comissao(8), 'alerta')
        self.assertEqual(indicadores.classificar_vencimento_comissao(15), 'alerta')
        self.assertEqual(indicadores.classificar_vencimento_comissao(16), 'normal')

    def test_limites_vencimento_contrato(self):
        self.assertEqual(indicadores.classificar_vencimento_contrato(90), 'ate_90')
        self.assertEqual(indicadores.classificar_vencimento_contrato(91), 'entre_90_120')
        self.assertEqual(indicadores.classificar_vencimento_contrato(120), 'entre_90_120')
        self.assertEqual(indicadores.classificar_vencimento_contrato(121), 'apos_120')

    def test_limites_qualificacao(self):
        hoje = date(2026, 6, 1)
        limite = hoje - timedelta(days=DIAS_VALIDADE_QUALIFICACAO)
        self.assertEqual(indicadores.classificar_qualificacao(None, hoje), 'sem_curso')
        self.assertEqual(indicadores.classificar_qualificacao(limite, hoje), 'em_dia')
        self.assertEqual(indicadores.classificar_qualificacao(limite - timedelta(days=1), hoje), 'vencidos')

    def test_limites_permanencia(self):
        self.assertEqual(indicadores.classificar_permanencia(365), 'bg-success')
        self.assertEqual(indicadores.classificar_permanencia(366), 'bg-warning text-dark')
        self.assertEqual(indicadores.classificar_permanencia(730), 'bg-warning text-dark')
        self.assertEqual(indicadores.classificar_permanencia(731), 'bg-danger')


class BaseDrillTest(TestCase):
    def setUp(self):
        self.hoje = date.today()
        self.posto = PostoGraduacao.objects.create(sigla='Cap', descricao='Capitão', senioridade=3)
        self.fiscal = Funcao.objects.create(titulo='Fiscal', sigla='FIS')
        self.empresa = Empresa.objects.create(razao_social='Empresa Drill', cnpj='12.345.678/0001-90')

        self.ag_em_dia = Agente.objects.create(
            nome_completo='Ana Em Dia', nome_de_guerra='Ana', posto=self.posto, saram='1001',
            data_ultimo_curso=self.hoje - timedelta(days=30))
        self.ag_sem_curso = Agente.objects.create(
            nome_completo='Beto Sem Curso', nome_de_guerra='Beto', posto=self.posto, saram='1002')

        # Contrato que vence em 5 dias (comissão crítica e contrato <= 90 dias)
        self.c_critico = self._contrato('001/2026', 5)
        # Contrato que vence em 100 dias (comissão normal e contrato 90-120)
        self.c_medio = self._contrato('002/2026', 100)
        # Contrato sem fiscal (em risco)
        self.c_risco = self._contrato('003/2026', 200)

        self._designar(self.c_critico, self.ag_em_dia, inicio_dias=400)
        self._designar(self.c_medio, self.ag_em_dia, inicio_dias=50)
        self._designar(self.c_medio, self.ag_sem_curso, inicio_dias=10)

    def _contrato(self, numero, dias):
        return Contrato.objects.create(
            numero=numero, tipo='DESPESA', empresa=self.empresa, objeto='Objeto',
            vigencia_inicio=self.hoje - timedelta(days=500),
            vigencia_fim=self.hoje + timedelta(days=dias), valor_total=1000)

    def _designar(self, contrato, agente, inicio_dias, fim=None, desligamento=None):
        comissao, _ = Comissao.objects.get_or_create(contrato=contrato, tipo='FISCALIZACAO', defaults={'ativa': True})
        return Integrante.objects.create(
            comissao=comissao, agente=agente, funcao=self.fiscal,
            data_inicio=self.hoje - timedelta(days=inicio_dias), data_fim=fim,
            data_desligamento=desligamento, portaria_numero='1', portaria_data=self.hoje)


class IndicadoresServicoTest(BaseDrillTest):
    def test_contagem_igual_ao_numero_de_linhas_do_detalhe(self):
        for chave in ('vencimento-comissoes', 'qualificacao', 'vencimento-contratos'):
            contagem = indicadores.contar(chave, self.hoje)
            for segmento, qtd in contagem.items():
                _, _, linhas = indicadores.detalhar(chave, segmento, self.hoje)
                self.assertEqual(len(linhas), qtd, f'{chave}:{segmento}')

    def test_vencimento_comissoes(self):
        self.assertEqual(indicadores.contar('vencimento-comissoes', self.hoje),
                         {'critico': 1, 'alerta': 0, 'normal': 1})

    def test_qualificacao(self):
        self.assertEqual(indicadores.contar('qualificacao', self.hoje),
                         {'em_dia': 1, 'vencidos': 0, 'sem_curso': 1})

    def test_contratos_risco(self):
        _, _, linhas = indicadores.detalhar('contratos-risco', 'todos', self.hoje)
        self.assertEqual([l.celulas[0] for l in linhas], ['003/2026'])

    def test_sobrecarga_por_fiscal(self):
        _, rotulo, linhas = indicadores.detalhar('sobrecarga', str(self.ag_em_dia.id), self.hoje)
        self.assertEqual(rotulo, 'Cap Ana')
        self.assertEqual(sorted(l.celulas[1] for l in linhas), ['001/2026', '002/2026'])

    def test_segmento_invalido(self):
        with self.assertRaises(ValueError):
            indicadores.detalhar('qualificacao', 'inexistente', self.hoje)
        with self.assertRaises(ValueError):
            indicadores.detalhar('sobrecarga', 'abc', self.hoje)
        with self.assertRaises(KeyError):
            indicadores.detalhar('nao-existe', 'todos', self.hoje)

    def test_radar_encadeia_designacoes_anteriores(self):
        # Designação anterior no mesmo contrato/função, terminando na véspera da atual.
        atual = Integrante.objects.get(comissao__contrato=self.c_medio, agente=self.ag_sem_curso)
        Integrante.objects.create(
            comissao=atual.comissao, agente=self.ag_sem_curso, funcao=self.fiscal,
            data_inicio=atual.data_inicio - timedelta(days=300),
            data_fim=atual.data_inicio - timedelta(days=1),
            portaria_numero='0', portaria_data=self.hoje)
        radar = indicadores.radar_permanencia(self.hoje)
        item = next(i for i in radar if i['agente'] == self.ag_sem_curso)
        self.assertEqual(item['inicio_real'], atual.data_inicio - timedelta(days=300))
        self.assertEqual(item['dias_totais'], 310)

    def test_radar_usa_numero_fixo_de_consultas(self):
        for n in range(5):
            ag = Agente.objects.create(nome_completo=f'Extra {n}', nome_de_guerra=f'Extra{n}',
                                       posto=self.posto, saram=f'20{n}')
            self._designar(self.c_risco, ag, inicio_dias=20)
        with self.assertNumQueries(2):
            indicadores.radar_permanencia(self.hoje)


class DetalheEndpointTest(BaseDrillTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('auditor_drill', password='senha-teste-123')
        self.user.groups.add(Group.objects.get_or_create(name='Auditores')[0])
        self.client.login(username='auditor_drill', password='senha-teste-123')

    def _url(self, indicador, **params):
        url = reverse('detalhe_indicador', args=[indicador])
        if params:
            url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
        return url

    def test_fragmento_lista_registros_do_segmento(self):
        resp = self.client.get(self._url('vencimento-comissoes', segmento='critico'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'contratos/auditoria/_detalhe.html')
        self.assertContains(resp, '001/2026')
        self.assertNotContains(resp, '002/2026')
        self.assertContains(resp, reverse('detalhe_contrato_portal', args=[self.c_critico.id]))

    def test_sem_segmento_lista_todos(self):
        resp = self.client.get(self._url('contratos-vigentes'))
        self.assertEqual(resp.status_code, 200)
        for numero in ('001/2026', '002/2026', '003/2026'):
            self.assertContains(resp, numero)

    def test_indicador_ou_segmento_invalido_retorna_400(self):
        self.assertEqual(self.client.get(self._url('nao-existe')).status_code, 400)
        self.assertEqual(self.client.get(self._url('qualificacao', segmento='xyz')).status_code, 400)

    def test_exportacao_do_recorte(self):
        resp = self.client.get(self._url('qualificacao', segmento='sem_curso', formato='csv'))
        self.assertEqual(resp.status_code, 200)
        conteudo = resp.content.decode('utf-8-sig')
        self.assertIn('Beto', conteudo)
        self.assertNotIn('Ana', conteudo)
        self.assertIn('detalhe_qualificacao_sem-curso.csv', resp['Content-Disposition'])

    def test_anonimo_e_redirecionado(self):
        self.client.logout()
        resp = self.client.get(self._url('qualificacao', segmento='em_dia'))
        self.assertEqual(resp.status_code, 302)

    def test_usuario_sem_perfil_auditor_nao_ve_link_do_contrato(self):
        User.objects.create_user('comum_drill', password='senha-teste-123')
        self.client.login(username='comum_drill', password='senha-teste-123')
        resp = self.client.get(self._url('vencimento-comissoes', segmento='critico'))
        self.assertContains(resp, '001/2026')
        self.assertNotContains(resp, reverse('detalhe_contrato_portal', args=[self.c_critico.id]))

    def test_painel_expoe_ids_e_painel_lateral(self):
        resp = self.client.get(reverse('painel_controle'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="offcanvasDetalhe"')
        self.assertContains(resp, 'dashboard-drill.js')
        self.assertContains(resp, f'[{self.ag_em_dia.id}')  # ids da sobrecarga/permanência
