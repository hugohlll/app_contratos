import json
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.db import IntegrityError

from contratos.models import (
    CalendarioPrestacao, Contrato, Empresa, Agente, PostoGraduacao,
    Comissao, Integrante, Funcao
)


class CalendarioPrestacaoModelTest(TestCase):
    """Testes para o model CalendarioPrestacao."""

    def test_criacao_basica(self):
        """Testa criação de um registro no calendário."""
        cal = CalendarioPrestacao.objects.create(
            ano=2026, mes=5,
            data_entrega=date(2026, 5, 10),
            data_apresentacao=date(2026, 5, 15)
        )
        self.assertEqual(cal.ano, 2026)
        self.assertEqual(cal.mes, 5)
        self.assertEqual(cal.data_entrega, date(2026, 5, 10))
        self.assertEqual(cal.data_apresentacao, date(2026, 5, 15))

    def test_str_representation(self):
        """Testa a representação em string do calendário."""
        cal = CalendarioPrestacao.objects.create(ano=2026, mes=3)
        self.assertEqual(str(cal), "03/2026")

    def test_str_representation_mes_dois_digitos(self):
        """Testa a representação em string para meses de um dígito."""
        cal = CalendarioPrestacao.objects.create(ano=2026, mes=12)
        self.assertEqual(str(cal), "12/2026")

    def test_datas_opcionais(self):
        """Testa que as datas podem ser nulas."""
        cal = CalendarioPrestacao.objects.create(ano=2026, mes=7)
        self.assertIsNone(cal.data_entrega)
        self.assertIsNone(cal.data_apresentacao)

    def test_unique_together_ano_mes(self):
        """Testa que não é possível criar dois registros para o mesmo ano/mês."""
        CalendarioPrestacao.objects.create(ano=2026, mes=1)
        with self.assertRaises(IntegrityError):
            CalendarioPrestacao.objects.create(ano=2026, mes=1)

    def test_ordering_por_ano_e_mes(self):
        """Testa que a ordenação padrão é por ano e mês."""
        CalendarioPrestacao.objects.create(ano=2026, mes=12)
        CalendarioPrestacao.objects.create(ano=2026, mes=1)
        CalendarioPrestacao.objects.create(ano=2025, mes=6)

        calendarios = list(CalendarioPrestacao.objects.all())
        self.assertEqual(calendarios[0].ano, 2025)
        self.assertEqual(calendarios[0].mes, 6)
        self.assertEqual(calendarios[1].ano, 2026)
        self.assertEqual(calendarios[1].mes, 1)
        self.assertEqual(calendarios[2].ano, 2026)
        self.assertEqual(calendarios[2].mes, 12)


class SalvarCalendarioPrestacaoViewTest(TestCase):
    """Testes para a view salvar_calendario_prestacao."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('salvar_calendario_prestacao')

        # Usuário normal (sem permissões)
        self.user_normal = User.objects.create_user(
            username='normal', password='password123'
        )

        # Auditor
        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        self.user_auditor = User.objects.create_user(
            username='auditor', password='password123'
        )
        self.user_auditor.groups.add(grupo_auditores)

        # Admin (superuser)
        self.user_admin = User.objects.create_superuser(
            username='admin', email='admin@test.com', password='password123'
        )

    def _post_json(self, data):
        """Helper para enviar POST com JSON."""
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type='application/json'
        )

    def test_sem_login_redireciona(self):
        """Sem autenticação, deve redirecionar para login."""
        response = self._post_json({'ano': 2026, 'mes': 5})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_usuario_normal_negado(self):
        """Usuário sem grupo Auditores nem superuser deve receber 403."""
        self.client.login(username='normal', password='password123')
        response = self._post_json({
            'ano': 2026, 'mes': 5,
            'data_entrega': '2026-05-10',
            'data_apresentacao': '2026-05-15'
        })
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])

    def test_auditor_pode_salvar(self):
        """Auditor deve conseguir salvar datas no calendário."""
        self.client.login(username='auditor', password='password123')
        response = self._post_json({
            'ano': 2026, 'mes': 5,
            'data_entrega': '2026-05-10',
            'data_apresentacao': '2026-05-15'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        # Verifica no banco
        cal = CalendarioPrestacao.objects.get(ano=2026, mes=5)
        self.assertEqual(cal.data_entrega, date(2026, 5, 10))
        self.assertEqual(cal.data_apresentacao, date(2026, 5, 15))

    def test_admin_pode_salvar(self):
        """Admin (superuser) deve conseguir salvar datas no calendário."""
        self.client.login(username='admin', password='password123')
        response = self._post_json({
            'ano': 2026, 'mes': 8,
            'data_entrega': '2026-08-05',
            'data_apresentacao': '2026-08-20'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        cal = CalendarioPrestacao.objects.get(ano=2026, mes=8)
        self.assertEqual(cal.data_entrega, date(2026, 8, 5))
        self.assertEqual(cal.data_apresentacao, date(2026, 8, 20))

    def test_atualizar_datas_existentes(self):
        """Se já existir um registro, deve atualizar as datas em vez de criar novo."""
        CalendarioPrestacao.objects.create(
            ano=2026, mes=3,
            data_entrega=date(2026, 3, 1),
            data_apresentacao=date(2026, 3, 10)
        )

        self.client.login(username='auditor', password='password123')
        response = self._post_json({
            'ano': 2026, 'mes': 3,
            'data_entrega': '2026-03-15',
            'data_apresentacao': '2026-03-25'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # Deve ter apenas 1 registro (atualizado, não duplicado)
        self.assertEqual(CalendarioPrestacao.objects.filter(ano=2026, mes=3).count(), 1)
        cal = CalendarioPrestacao.objects.get(ano=2026, mes=3)
        self.assertEqual(cal.data_entrega, date(2026, 3, 15))
        self.assertEqual(cal.data_apresentacao, date(2026, 3, 25))

    def test_limpar_datas(self):
        """Enviar datas vazias deve limpar os campos (setar como null)."""
        CalendarioPrestacao.objects.create(
            ano=2026, mes=6,
            data_entrega=date(2026, 6, 1),
            data_apresentacao=date(2026, 6, 10)
        )

        self.client.login(username='auditor', password='password123')
        response = self._post_json({
            'ano': 2026, 'mes': 6,
            'data_entrega': '',
            'data_apresentacao': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        cal = CalendarioPrestacao.objects.get(ano=2026, mes=6)
        self.assertIsNone(cal.data_entrega)
        self.assertIsNone(cal.data_apresentacao)

    def test_metodo_get_nao_permitido(self):
        """GET deve ser rejeitado (a view usa @require_POST)."""
        self.client.login(username='auditor', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class DashboardCalendarioRenderingTest(TestCase):
    """Testa se o calendário aparece corretamente no dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user_dash', password='password123')

        # Setup mínimo para o dashboard não quebrar
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Teste", cnpj="12.345.678/0001-90"
        )
        self.contrato = Contrato.objects.create(
            numero="001/2026", empresa=self.empresa, objeto="Teste",
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=1000.00
        )

    def test_dashboard_exibe_tabela_calendario(self):
        """O dashboard deve renderizar a seção do calendário anual."""
        self.client.login(username='user_dash', password='password123')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calendário Anual de Prestação de Contas')
        self.assertContains(response, 'Data de Entrega dos Slides')
        self.assertContains(response, 'Data Prevista para Apresentação')

    def test_dashboard_calendario_exibe_12_meses(self):
        """O calendário deve conter os 12 meses do ano."""
        self.client.login(username='user_dash', password='password123')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)

        calendario = response.context['calendario_anual']
        self.assertEqual(len(calendario), 12)

        # Verifica que todos os meses de 1 a 12 estão presentes
        meses = [c['mes'] for c in calendario]
        self.assertEqual(meses, list(range(1, 13)))

    def test_dashboard_calendario_com_datas_preenchidas(self):
        """Datas salvas no banco devem aparecer nos inputs do calendário."""
        CalendarioPrestacao.objects.create(
            ano=date.today().year, mes=5,
            data_entrega=date(date.today().year, 5, 10),
            data_apresentacao=date(date.today().year, 5, 20)
        )

        self.client.login(username='user_dash', password='password123')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)

        calendario = response.context['calendario_anual']
        maio = next(c for c in calendario if c['mes'] == 5)
        self.assertEqual(maio['data_entrega'], f'{date.today().year}-05-10')
        self.assertEqual(maio['data_apresentacao'], f'{date.today().year}-05-20')

    def test_dashboard_calendario_inputs_disabled_para_usuario_comum(self):
        """Usuário sem permissão de admin/auditor deve ver os inputs desabilitados."""
        self.client.login(username='user_dash', password='password123')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'disabled')

    def test_dashboard_calendario_inputs_habilitados_para_auditor(self):
        """Auditor deve ver os inputs do calendário habilitados (sem 'disabled')."""
        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        user_auditor = User.objects.create_user(
            username='auditor_dash', password='password123'
        )
        user_auditor.groups.add(grupo_auditores)

        self.client.login(username='auditor_dash', password='password123')
        response = self.client.get(reverse('dashboard_prestacao'))
        self.assertEqual(response.status_code, 200)

        # Os inputs de calendário NÃO devem ter o atributo 'disabled'
        content = response.content.decode('utf-8')
        # Verifica que cal-input aparece sem disabled (pelo menos um)
        self.assertIn('cal-input', content)
        # Conta inputs com disabled e sem — para auditor, nenhum cal-input deve ter disabled
        import re
        cal_inputs = re.findall(r'<input[^>]*cal-input[^>]*>', content)
        for cal_input in cal_inputs:
            self.assertNotIn('disabled', cal_input)
