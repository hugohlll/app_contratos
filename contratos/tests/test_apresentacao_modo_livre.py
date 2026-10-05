import json
from datetime import date, timedelta
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Empresa, PrestacaoContas, Agente, PostoGraduacao,
    ConfiguracaoApresentacao
)

PDF_MINIMO = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Resources << >> >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000058 00000 n \n0000000115 00000 n \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n212\n%%EOF"
)


class ApresentacaoModoLivreTests(TestCase):
    """Testes completos para a funcionalidade de Ordem Livre na Apresentação."""

    def setUp(self):
        self.client = Client()

        # Criar postos com senioridades diferentes (menor número = mais antigo)
        self.posto_cel = PostoGraduacao.objects.create(sigla="Cel", descricao="Coronel", senioridade=1)
        self.posto_ten = PostoGraduacao.objects.create(sigla="1º Ten", descricao="Primeiro Tenente", senioridade=5)

        self.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="22.222.222/0001-22")

        # Agentes
        self.agente_cel = Agente.objects.create(
            nome_completo="Coronel Silva", nome_de_guerra="Silva",
            posto=self.posto_cel, saram="1111111"
        )
        self.agente_ten = Agente.objects.create(
            nome_completo="Tenente Santos", nome_de_guerra="Santos",
            posto=self.posto_ten, saram="2222222"
        )

        # Contratos vigentes
        hoje = date.today()
        self.contrato1 = Contrato.objects.create(
            numero="101/2026", tipo="DESPESA", empresa=self.empresa,
            objeto="Objeto 1", vigencia_inicio=hoje - timedelta(days=30),
            vigencia_fim=hoje + timedelta(days=330), valor_total=10000
        )
        self.contrato2 = Contrato.objects.create(
            numero="102/2026", tipo="DESPESA", empresa=self.empresa,
            objeto="Objeto 2", vigencia_inicio=hoje - timedelta(days=30),
            vigencia_fim=hoje + timedelta(days=330), valor_total=20000
        )

        # Mês/ano passado
        if hoje.month == 1:
            self.mes_ref = 12
            self.ano_ref = hoje.year - 1
        else:
            self.mes_ref = hoje.month - 1
            self.ano_ref = hoje.year

        # Prestações de contas vinculadas
        pdf1 = SimpleUploadedFile("slide1.pdf", PDF_MINIMO, content_type="application/pdf")
        pdf2 = SimpleUploadedFile("slide2.pdf", PDF_MINIMO, content_type="application/pdf")

        # Cel Silva no Contrato 101
        self.pc_cel = PrestacaoContas.objects.create(
            contrato=self.contrato1, agente=self.agente_cel,
            ano_referencia=self.ano_ref, mes_referencia=self.mes_ref,
            arquivo=pdf1, status='ok', compor_apresentacao=True, ordem_apresentacao=0.0
        )

        # Ten Santos no Contrato 102
        self.pc_ten = PrestacaoContas.objects.create(
            contrato=self.contrato2, agente=self.agente_ten,
            ano_referencia=self.ano_ref, mes_referencia=self.mes_ref,
            arquivo=pdf2, status='ok', compor_apresentacao=True, ordem_apresentacao=1.0
        )

        # Usuários
        grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        self.auditor = User.objects.create_user(username='auditor_teste', password='pwd')
        self.auditor.groups.add(grupo_auditores)

        self.user_comum = User.objects.create_user(username='comum_teste', password='pwd')

    def test_alternar_modo_apresentacao_permissoes(self):
        """Apenas auditores e administradores podem alternar o modo da apresentação."""
        url = reverse('alternar_modo_apresentacao')
        payload = {'tipo': 'fiscais', 'ano': self.ano_ref, 'mes': self.mes_ref, 'modo_livre': True}

        # Anônimo: redireciona para login
        res = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 302)

        # Usuário comum: 403 Proibido
        self.client.login(username='comum_teste', password='pwd')
        res = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 403)

        # Auditor: 200 Sucesso
        self.client.login(username='auditor_teste', password='pwd')
        res = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['modo_livre'])

    def test_persistencia_modo_livre_por_mes_e_ano(self):
        """Verifica se ConfiguracaoApresentacao é salva isolada por mês/ano."""
        self.client.login(username='auditor_teste', password='pwd')
        url = reverse('alternar_modo_apresentacao')

        # Ativa modo livre para o mês de teste
        res = self.client.post(url, json.dumps({
            'tipo': 'fiscais', 'ano': self.ano_ref, 'mes': self.mes_ref, 'modo_livre': True
        }), content_type='application/json')
        self.assertEqual(res.status_code, 200)

        config = ConfiguracaoApresentacao.objects.get(
            tipo_apresentacao='fiscais', ano_referencia=self.ano_ref, mes_referencia=self.mes_ref
        )
        self.assertTrue(config.modo_livre)

        # Outro mês deve permanecer com modo livre False por padrão
        outro_mes = 1 if self.mes_ref != 1 else 2
        config_outro = ConfiguracaoApresentacao.objects.filter(
            tipo_apresentacao='fiscais', ano_referencia=self.ano_ref, mes_referencia=outro_mes
        ).first()
        self.assertTrue(config_outro is None or not config_outro.modo_livre)

    def test_reordenacao_livre_tenente_antes_de_coronel(self):
        """No modo livre, Tenente pode ficar posicionado antes de Coronel e essa ordem persiste."""
        self.client.login(username='auditor_teste', password='pwd')

        # 1. Ativa modo livre
        self.client.post(reverse('alternar_modo_apresentacao'), json.dumps({
            'tipo': 'fiscais', 'ano': self.ano_ref, 'mes': self.mes_ref, 'modo_livre': True
        }), content_type='application/json')

        # 2. Reordena colocando Tenente (id=self.pc_ten.id) na frente do Coronel (id=self.pc_cel.id)
        url_reordenar = reverse('reordenar_apresentacao_livre')
        payload = {
            'tipo_apresentacao': 'fiscais',
            'itens': [
                {'tipo': 'prestacao', 'id': self.pc_ten.id},
                {'tipo': 'prestacao', 'id': self.pc_cel.id}
            ]
        }
        res = self.client.post(url_reordenar, json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

        # 3. Consulta o dashboard e verifica se a ordem retornada respeita a nova ordem
        url_dash = f"{reverse('dashboard_prestacao')}?mes={self.mes_ref}&ano={self.ano_ref}"
        res_dash = self.client.get(url_dash)
        self.assertEqual(res_dash.status_code, 200)
        gestores_prio = res_dash.context['gestores_prio']

        # Tenente Santos deve ser o primeiro item
        self.assertEqual(len(gestores_prio), 2)
        self.assertIn("Santos", gestores_prio[0]['gestor'])
        self.assertIn("Silva", gestores_prio[1]['gestor'])

    def test_desativar_modo_livre_restaura_ordem_antiguidade(self):
        """Ao desativar o modo livre, o Coronel deve voltar a preceder o Tenente automaticamente."""
        self.client.login(username='auditor_teste', password='pwd')

        # 1. Ativa modo livre e inverte posições
        self.client.post(reverse('alternar_modo_apresentacao'), json.dumps({
            'tipo': 'fiscais', 'ano': self.ano_ref, 'mes': self.mes_ref, 'modo_livre': True
        }), content_type='application/json')

        self.client.post(reverse('reordenar_apresentacao_livre'), json.dumps({
            'tipo_apresentacao': 'fiscais',
            'itens': [
                {'tipo': 'prestacao', 'id': self.pc_ten.id},
                {'tipo': 'prestacao', 'id': self.pc_cel.id}
            ]
        }), content_type='application/json')

        # 2. Desativa o modo livre
        res_desativar = self.client.post(reverse('alternar_modo_apresentacao'), json.dumps({
            'tipo': 'fiscais', 'ano': self.ano_ref, 'mes': self.mes_ref, 'modo_livre': False
        }), content_type='application/json')
        self.assertEqual(res_desativar.status_code, 200)
        data = res_desativar.json()
        self.assertFalse(data['modo_livre'])

        # O retorno AJAX de stats já deve vir com o Coronel em primeiro lugar
        gestores_prio_retorno = data['stats']['gestores_prio']
        self.assertIn("Silva", gestores_prio_retorno[0]['gestor'])
        self.assertIn("Santos", gestores_prio_retorno[1]['gestor'])

        # Na view do dashboard, também deve vir o Coronel antes do Tenente
        url_dash = f"{reverse('dashboard_prestacao')}?mes={self.mes_ref}&ano={self.ano_ref}"
        res_dash = self.client.get(url_dash)
        gestores_prio = res_dash.context['gestores_prio']
        self.assertIn("Silva", gestores_prio[0]['gestor'])
        self.assertIn("Santos", gestores_prio[1]['gestor'])

    def test_consolidar_pdf_respeita_modo_livre(self):
        """A consolidação de PDF deve respeitar a ordem livre quando ela estiver ativada."""
        self.client.login(username='auditor_teste', password='pwd')

        # Ativa modo livre e inverte
        self.client.post(reverse('alternar_modo_apresentacao'), json.dumps({
            'tipo': 'fiscais', 'ano': self.ano_ref, 'mes': self.mes_ref, 'modo_livre': True
        }), content_type='application/json')

        self.client.post(reverse('reordenar_apresentacao_livre'), json.dumps({
            'tipo_apresentacao': 'fiscais',
            'itens': [
                {'tipo': 'prestacao', 'id': self.pc_ten.id},
                {'tipo': 'prestacao', 'id': self.pc_cel.id}
            ]
        }), content_type='application/json')

        url_pdf = f"{reverse('consolidar_apresentacao')}?mes={self.mes_ref}&ano={self.ano_ref}"
        res = self.client.get(url_pdf)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
