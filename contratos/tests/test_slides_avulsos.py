import os
import json
from datetime import date, timedelta
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Empresa, PrestacaoContas, Agente, PostoGraduacao,
    Comissao, Integrante, Funcao, SlideApresentacao,
    Setor, PrestacaoContasSetor
)

# PDF mínimo válido para pypdf
PDF_MINIMO = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Resources << >> >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000058 00000 n \n0000000115 00000 n \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n212\n%%EOF"
)


class SlideAvulsoBaseTestCase(TestCase):
    """Setup compartilhado para todos os testes de slides avulsos."""

    def setUp(self):
        self.client = Client()
        self.posto = PostoGraduacao.objects.create(sigla="Cap", descricao="Capitão", senioridade=3)
        self.empresa = Empresa.objects.create(razao_social="Empresa Slide", cnpj="11.111.111/0001-11")
        self.agente = Agente.objects.create(
            nome_completo="Agente Slide", nome_de_guerra="Slide",
            posto=self.posto, saram="7777777"
        )
        self.contrato = Contrato.objects.create(
            numero="050/2026", tipo="DESPESA", empresa=self.empresa,
            objeto="Objeto Slide", vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365), valor_total=5000
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO', ativa=True, data_inicio=date.today()
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal", ordem=1)
        Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date.today(), portaria_numero="500", portaria_data=date.today()
        )

        # Auditor
        grupo, _ = Group.objects.get_or_create(name='Auditores')
        self.auditor = User.objects.create_user(username='auditor_slide', password='pass123')
        self.auditor.groups.add(grupo)

        # Usuário comum
        self.user_normal = User.objects.create_user(username='normal_slide', password='pass123')

        self.mes_ref = 5
        self.ano_ref = 2026

    def _login_auditor(self):
        self.client.login(username='auditor_slide', password='pass123')

    def _login_normal(self):
        self.client.login(username='normal_slide', password='pass123')

    def _upload_slide(self, tipo='fiscais', nome='Capa', mes=None, ano=None):
        """Helper: faz upload de um slide avulso via POST."""
        pdf = SimpleUploadedFile("slide.pdf", PDF_MINIMO, content_type="application/pdf")
        return self.client.post(reverse('upload_slide_avulso'), {
            'tipo_apresentacao': tipo,
            'nome_slide': nome,
            'mes_referencia': mes or self.mes_ref,
            'ano_referencia': ano or self.ano_ref,
            'arquivo': pdf
        })

    def _cleanup_slides(self):
        for s in SlideApresentacao.objects.all():
            if s.arquivo and os.path.isfile(s.arquivo.path):
                os.remove(s.arquivo.path)

    def _cleanup_prestacoes(self):
        for p in PrestacaoContas.objects.all():
            if p.arquivo and os.path.isfile(p.arquivo.path):
                os.remove(p.arquivo.path)
        for p in PrestacaoContasSetor.objects.all():
            if p.arquivo and os.path.isfile(p.arquivo.path):
                os.remove(p.arquivo.path)

    def tearDown(self):
        self._cleanup_slides()
        self._cleanup_prestacoes()


# ─── UPLOAD ────────────────────────────────────────────────────────────────────

class UploadSlideAvulsoTests(SlideAvulsoBaseTestCase):

    def test_upload_requer_login(self):
        """Endpoint de upload deve redirecionar usuários não autenticados."""
        response = self._upload_slide()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_upload_usuario_normal_negado(self):
        """Usuários sem permissão de auditor devem receber 403."""
        self._login_normal()
        response = self._upload_slide()
        self.assertEqual(response.status_code, 403)

    def test_upload_sucesso(self):
        """Auditor deve conseguir fazer upload de um slide avulso."""
        self._login_auditor()
        response = self._upload_slide(nome='Capa Fiscais')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['slide']['nome'], 'Capa Fiscais')
        self.assertEqual(SlideApresentacao.objects.count(), 1)

    def test_upload_apenas_pdf(self):
        """Apenas arquivos PDF devem ser aceitos."""
        self._login_auditor()
        txt = SimpleUploadedFile("slide.txt", b"conteudo", content_type="text/plain")
        response = self.client.post(reverse('upload_slide_avulso'), {
            'tipo_apresentacao': 'fiscais',
            'nome_slide': 'Inválido',
            'mes_referencia': self.mes_ref,
            'ano_referencia': self.ano_ref,
            'arquivo': txt
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('PDF', response.json()['error'])

    def test_upload_campos_obrigatorios(self):
        """Deve retornar erro se faltar algum campo obrigatório."""
        self._login_auditor()
        response = self.client.post(reverse('upload_slide_avulso'), {
            'tipo_apresentacao': 'fiscais',
            'mes_referencia': self.mes_ref,
            'ano_referencia': self.ano_ref,
            # Faltando nome_slide e arquivo
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_ano_formatado_com_ponto(self):
        """O campo ano pode vir com separador de milhar (ex: 2.026) da localização pt-BR."""
        self._login_auditor()
        pdf = SimpleUploadedFile("slide.pdf", PDF_MINIMO, content_type="application/pdf")
        response = self.client.post(reverse('upload_slide_avulso'), {
            'tipo_apresentacao': 'fiscais',
            'nome_slide': 'Capa pt-BR',
            'mes_referencia': self.mes_ref,
            'ano_referencia': '2.026',
            'arquivo': pdf
        })
        self.assertEqual(response.status_code, 200)
        slide = SlideApresentacao.objects.first()
        self.assertEqual(slide.ano_referencia, 2026)

    def test_upload_indice_posicao_incremental(self):
        """Slides adicionados sequencialmente devem receber índices crescentes."""
        self._login_auditor()
        self._upload_slide(nome='Slide 1')
        self._upload_slide(nome='Slide 2')
        self._upload_slide(nome='Slide 3')

        slides = SlideApresentacao.objects.order_by('indice_posicao')
        indices = [s.indice_posicao for s in slides]
        self.assertEqual(len(indices), 3)
        self.assertTrue(indices[0] < indices[1] < indices[2])


# ─── EXCLUSÃO ──────────────────────────────────────────────────────────────────

class ExcluirSlideAvulsoTests(SlideAvulsoBaseTestCase):

    def test_excluir_requer_login(self):
        """Exclusão de slide deve redirecionar não autenticados."""
        self._login_auditor()
        self._upload_slide()
        self.client.logout()
        slide = SlideApresentacao.objects.first()
        response = self.client.post(reverse('excluir_slide_avulso', args=[slide.pk]))
        self.assertEqual(response.status_code, 302)

    def test_excluir_usuario_normal_negado(self):
        """Usuários sem permissão devem receber 403."""
        self._login_auditor()
        self._upload_slide()
        slide = SlideApresentacao.objects.first()
        self._login_normal()
        response = self.client.post(reverse('excluir_slide_avulso', args=[slide.pk]))
        self.assertEqual(response.status_code, 403)

    def test_excluir_sucesso(self):
        """Auditor deve conseguir excluir um slide avulso."""
        self._login_auditor()
        self._upload_slide()
        self.assertEqual(SlideApresentacao.objects.count(), 1)
        slide = SlideApresentacao.objects.first()
        response = self.client.post(reverse('excluir_slide_avulso', args=[slide.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(SlideApresentacao.objects.count(), 0)

    def test_excluir_slide_inexistente(self):
        """Excluir slide com pk inexistente deve retornar 404."""
        self._login_auditor()
        response = self.client.post(reverse('excluir_slide_avulso', args=[99999]))
        self.assertEqual(response.status_code, 404)


# ─── REORDENAÇÃO ───────────────────────────────────────────────────────────────

class ReordenarSlideAvulsoTests(SlideAvulsoBaseTestCase):

    def test_reordenar_requer_login(self):
        response = self.client.post(
            reverse('reordenar_slide_avulso'),
            data=json.dumps({'slide_id': 1, 'new_index': 0}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 302)

    def test_reordenar_sucesso(self):
        """Reordenar deve atualizar o indice_posicao do slide."""
        self._login_auditor()
        self._upload_slide(nome='Slide Reord')
        slide = SlideApresentacao.objects.first()

        response = self.client.post(
            reverse('reordenar_slide_avulso'),
            data=json.dumps({'slide_id': slide.id, 'new_index': 0}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        slide.refresh_from_db()
        self.assertEqual(slide.indice_posicao, 0.0)


# ─── DASHBOARD (CONTEXTO) ─────────────────────────────────────────────────────

class DashboardSlideAvulsoTests(SlideAvulsoBaseTestCase):

    def test_slide_aparece_no_contexto_gestores_prio(self):
        """Slides avulsos do tipo 'fiscais' devem aparecer em gestores_prio no dashboard."""
        self._login_auditor()
        self._upload_slide(tipo='fiscais', nome='Capa Dashboard')

        response = self.client.get(reverse('dashboard_prestacao'), {'mes': self.mes_ref, 'ano': self.ano_ref})
        self.assertEqual(response.status_code, 200)
        gestores_prio = response.context['gestores_prio']
        slides = [g for g in gestores_prio if g.get('is_slide')]
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]['nome_slide'], 'Capa Dashboard')

    def test_slide_aparece_no_contexto_gestores_setores(self):
        """Slides avulsos do tipo 'gestores' devem aparecer em gestores_setores no dashboard."""
        self._login_auditor()
        self._upload_slide(tipo='gestores', nome='Capa Setores')

        response = self.client.get(reverse('dashboard_prestacao'), {'mes': self.mes_ref, 'ano': self.ano_ref})
        self.assertEqual(response.status_code, 200)
        gestores_setores = response.context['gestores_setores']
        slides = [g for g in gestores_setores if g.get('is_slide')]
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]['nome_slide'], 'Capa Setores')

    def test_slide_renderizado_no_html(self):
        """O slide avulso deve ser renderizado no HTML do dashboard."""
        self._login_auditor()
        self._upload_slide(tipo='fiscais', nome='Slide Renderizado')

        response = self.client.get(reverse('dashboard_prestacao'), {'mes': self.mes_ref, 'ano': self.ano_ref})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Slide Renderizado')
        self.assertContains(response, 'Slide Avulso')

    def test_slide_nao_aparece_em_outro_mes(self):
        """Slide do mês 5 não deve aparecer no dashboard do mês 6."""
        self._login_auditor()
        self._upload_slide(tipo='fiscais', nome='Slide Mês 5', mes=5)

        response = self.client.get(reverse('dashboard_prestacao'), {'mes': 6, 'ano': self.ano_ref})
        gestores_prio = response.context['gestores_prio']
        slides = [g for g in gestores_prio if g.get('is_slide')]
        self.assertEqual(len(slides), 0)


# ─── CONSOLIDAÇÃO PDF ─────────────────────────────────────────────────────────

class ConsolidarComSlideAvulsoTests(SlideAvulsoBaseTestCase):

    def test_consolidar_fiscais_somente_slides(self):
        """PDF consolidado deve funcionar mesmo com apenas slides avulsos (sem prestações)."""
        self._login_auditor()
        self._upload_slide(tipo='fiscais', nome='Capa Só Slide')

        response = self.client.get(
            reverse('consolidar_apresentacao'), {'mes': self.mes_ref, 'ano': self.ano_ref}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_consolidar_fiscais_slides_e_prestacoes(self):
        """PDF consolidado deve incluir tanto slides avulsos quanto prestações em conformidade."""
        self._login_auditor()
        self._upload_slide(tipo='fiscais', nome='Capa Mista')

        # Criar prestação em conformidade
        pdf = SimpleUploadedFile("prest.pdf", PDF_MINIMO, content_type="application/pdf")
        PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=self.mes_ref, ano_referencia=self.ano_ref,
            arquivo=pdf, status='ok', compor_apresentacao=True
        )

        response = self.client.get(
            reverse('consolidar_apresentacao'), {'mes': self.mes_ref, 'ano': self.ano_ref}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        # Deve ter pelo menos 2 páginas (1 do slide + 1 da prestação)
        self.assertTrue(len(response.content) > 100)

    def test_consolidar_setores_somente_slides(self):
        """PDF consolidado de setores deve funcionar apenas com slides avulsos."""
        self._login_auditor()
        self._upload_slide(tipo='gestores', nome='Capa Setores')

        response = self.client.get(
            reverse('consolidar_apresentacao_setor'), {'mes': self.mes_ref, 'ano': self.ano_ref}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_consolidar_setores_slides_e_prestacoes(self):
        """PDF consolidado de setores com slides + prestações em conformidade."""
        self._login_auditor()
        self._upload_slide(tipo='gestores', nome='Capa Setor Mista')

        setor = Setor.objects.create(nome="Setor Consolida", sigla="STC")
        pdf = SimpleUploadedFile("prest_setor.pdf", PDF_MINIMO, content_type="application/pdf")
        PrestacaoContasSetor.objects.create(
            setor=setor, agente=self.agente,
            mes_referencia=self.mes_ref, ano_referencia=self.ano_ref,
            arquivo=pdf, status='ok', compor_apresentacao=True
        )

        response = self.client.get(
            reverse('consolidar_apresentacao_setor'), {'mes': self.mes_ref, 'ano': self.ano_ref}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')


# ─── MODELO ────────────────────────────────────────────────────────────────────

class SlideApresentacaoModelTests(TestCase):

    def test_str_representation(self):
        """O __str__ do modelo deve exibir nome, tipo e período."""
        slide = SlideApresentacao(
            tipo_apresentacao='fiscais', ano_referencia=2026,
            mes_referencia=5, nome_slide='Capa'
        )
        resultado = str(slide)
        self.assertIn('Capa', resultado)
        self.assertIn('Fiscais', resultado)
        self.assertIn('05/2026', resultado)

    def test_ordering_padrao(self):
        """O ordering padrão deve ser por indice_posicao, data_registro."""
        pdf1 = SimpleUploadedFile("s1.pdf", b"%PDF", content_type="application/pdf")
        pdf2 = SimpleUploadedFile("s2.pdf", b"%PDF", content_type="application/pdf")
        SlideApresentacao.objects.create(
            tipo_apresentacao='fiscais', ano_referencia=2026, mes_referencia=5,
            nome_slide='Segundo', arquivo=pdf1, indice_posicao=2.0
        )
        SlideApresentacao.objects.create(
            tipo_apresentacao='fiscais', ano_referencia=2026, mes_referencia=5,
            nome_slide='Primeiro', arquivo=pdf2, indice_posicao=1.0
        )
        slides = list(SlideApresentacao.objects.all())
        self.assertEqual(slides[0].nome_slide, 'Primeiro')
        self.assertEqual(slides[1].nome_slide, 'Segundo')

        # Limpeza
        for s in slides:
            if s.arquivo and os.path.isfile(s.arquivo.path):
                os.remove(s.arquivo.path)
