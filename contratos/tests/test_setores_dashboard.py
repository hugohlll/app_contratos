import io
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfReader
from contratos.models import Setor, PrestacaoContasSetor, Agente, PostoGraduacao

class SetoresDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(username='admin_test', password='password123', email='admin@test.com')
        
        # Create auditor group and assign user to it
        self.auditor_group, _ = Group.objects.get_or_create(name="Auditores")
        self.user.groups.add(self.auditor_group)

        self.posto = PostoGraduacao.objects.create(descricao="Major", sigla="Maj", senioridade=1)
        self.agente = Agente.objects.create(
            nome_completo="Silva Alves",
            nome_de_guerra="Silva",
            posto=self.posto,
            saram="1234567"
        )
        
        self.setor1 = Setor.objects.create(nome="Setor Alfa", sigla="ALFA")
        self.setor2 = Setor.objects.create(nome="Setor Bravo", sigla="BRAV")
        self.setor3 = Setor.objects.create(nome="Setor Charlie", sigla="CHAR")
        
        # Create a valid 1-page PDF in memory
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        pdf_bytes = io.BytesIO()
        writer.write(pdf_bytes)
        pdf_bytes.seek(0)
        self.pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes.read(), content_type="application/pdf")
        
        self.hoje = date.today()

    def test_dashboard_setor_stats_and_list(self):
        """Test calculation of sector stats and sector presentation list on dashboard."""
        # Create different status submissions for sectors
        # Setor ALFA has status ok (in conformidade)
        PrestacaoContasSetor.objects.create(
            setor=self.setor1,
            mes_referencia=self.hoje.month,
            ano_referencia=self.hoje.year,
            status='ok',
            agente=self.agente,
            arquivo=self.pdf_file,
            compor_apresentacao=True
        )
        # Setor BRAV has status entregue (aguardando analise)
        PrestacaoContasSetor.objects.create(
            setor=self.setor2,
            mes_referencia=self.hoje.month,
            ano_referencia=self.hoje.year,
            status='entregue',
            agente=self.agente,
            compor_apresentacao=True
        )
        # Setor CHAR has no submission (should count as pendente)
        
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('dashboard_prestacao'), {'mes': self.hoje.month, 'ano': self.hoje.year})
        self.assertEqual(response.status_code, 200)
        
        context = response.context
        self.assertEqual(context['total_setores'], 3)
        self.assertEqual(context['ok_setores_no_mes'], 1)
        self.assertEqual(context['entregues_setores_no_mes'], 1)
        self.assertEqual(context['correcao_setores_no_mes'], 0)
        self.assertEqual(context['pendentes_setores_no_mes'], 1)
        
        # Gestores list should contain both submitted sectors (ALFA and BRAV)
        # regardless of prioritario flags (which sector model doesn't even have)
        self.assertEqual(len(context['gestores_setores']), 2)
        
        # Verify sectors are in the context presentation list
        sectors_in_list = [g['setor'] for g in context['gestores_setores']]
        self.assertIn("ALFA", sectors_in_list)
        self.assertIn("BRAV", sectors_in_list)

    def test_consolidar_apresentacao_setor(self):
        """Test the consolidation of sector PDFs in conformidade."""
        # Setor ALFA has status ok (in conformidade) and has a valid file
        PrestacaoContasSetor.objects.create(
            setor=self.setor1,
            mes_referencia=self.hoje.month,
            ano_referencia=self.hoje.year,
            status='ok',
            agente=self.agente,
            arquivo=self.pdf_file,
            compor_apresentacao=True
        )
        
        self.client.login(username='admin_test', password='password123')
        url = reverse('consolidar_apresentacao_setor') + f"?mes={self.hoje.month}&ano={self.hoje.year}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Read consolidated PDF content and verify it contains the page
        pdf_reader = PdfReader(io.BytesIO(response.content))
        self.assertEqual(len(pdf_reader.pages), 1)

    def test_consolidar_apresentacao_setor_no_ok(self):
        """Test consolidation when there are no sector PDFs in conformidade."""
        self.client.login(username='admin_test', password='password123')
        url = reverse('consolidar_apresentacao_setor') + f"?mes={self.hoje.month}&ano={self.hoje.year}"
        response = self.client.get(url)
        # Should redirect back to dashboard setores tab with warning
        self.assertRedirects(response, reverse('dashboard_prestacao') + f"?mes={self.hoje.month}&ano={self.hoje.year}&tab=setores")

    def test_alterar_status_setor_redireciona_com_tab_setores(self):
        """Testa se a alteração de status redireciona mantendo tab=setores e os filtros de data."""
        p = PrestacaoContasSetor.objects.create(
            setor=self.setor1, mes_referencia=self.hoje.month, ano_referencia=self.hoje.year,
            status='entregue', agente=self.agente
        )
        self.client.login(username='admin_test', password='password123')
        url = reverse('alterar_status_prestacao_setor', kwargs={'pk': p.id, 'novo_status': 'ok'})
        url_com_query = f"{url}?mes=5&ano=2026"
        response = self.client.get(url_com_query)
        self.assertRedirects(response, reverse('dashboard_prestacao') + "?tab=setores&mes=5&ano=2026")

    def test_excluir_setor_redireciona_com_tab_setores(self):
        """Testa se a exclusão de prestação redireciona mantendo tab=setores e os filtros de data."""
        p = PrestacaoContasSetor.objects.create(
            setor=self.setor1, mes_referencia=self.hoje.month, ano_referencia=self.hoje.year,
            status='entregue', agente=self.agente
        )
        self.client.login(username='admin_test', password='password123')
        url = reverse('excluir_prestacao_setor', kwargs={'pk': p.id})
        url_com_query = f"{url}?mes=6&ano=2026"
        response = self.client.post(url_com_query)
        self.assertRedirects(response, reverse('dashboard_prestacao') + "?tab=setores&mes=6&ano=2026")

    def test_consolidar_setor_nao_auditor_negado(self):
        """Testa se usuário sem permissão de auditor/admin recebe erro ao tentar consolidar PDFs."""
        user_normal = User.objects.create_user(username='normal_user_test', password='password123')
        self.client.login(username='normal_user_test', password='password123')
        url = reverse('consolidar_apresentacao_setor')
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)

    def test_consolidar_setor_sem_duplicacao_envios_multiplos(self):
        """Regressão: setor que enviou slides duas vezes não deve gerar duplicação na consolidação.

        Cenário real de produção: setor envia, auditor aprova como OK, setor reenvia
        (atualização), auditor aprova novamente. Apenas o envio mais recente deve ser
        consolidado no PDF final.
        """
        from pypdf import PdfWriter

        # Gera dois PDFs distintos (1 página cada)
        def _make_pdf():
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            buf = io.BytesIO()
            writer.write(buf)
            buf.seek(0)
            return SimpleUploadedFile("slide.pdf", buf.read(), content_type="application/pdf")

        # Primeiro envio: aprovado como OK com compor_apresentacao
        PrestacaoContasSetor.objects.create(
            setor=self.setor1,
            mes_referencia=self.hoje.month,
            ano_referencia=self.hoje.year,
            status='ok',
            agente=self.agente,
            arquivo=_make_pdf(),
            compor_apresentacao=True
        )

        # Segundo envio (atualização): também aprovado como OK, herda compor_apresentacao
        PrestacaoContasSetor.objects.create(
            setor=self.setor1,
            mes_referencia=self.hoje.month,
            ano_referencia=self.hoje.year,
            status='ok',
            agente=self.agente,
            arquivo=_make_pdf(),
            compor_apresentacao=True
        )

        # Confirma que existem 2 registros no BD para o mesmo setor/mês
        total = PrestacaoContasSetor.objects.filter(
            setor=self.setor1,
            mes_referencia=self.hoje.month,
            ano_referencia=self.hoje.year,
            status='ok',
            compor_apresentacao=True
        ).count()
        self.assertEqual(total, 2, "Setup: devem existir 2 registros OK no BD")

        self.client.login(username='admin_test', password='password123')
        url = reverse('consolidar_apresentacao_setor') + f"?mes={self.hoje.month}&ano={self.hoje.year}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        # O PDF consolidado deve conter apenas 1 página (somente o envio mais recente)
        pdf_reader = PdfReader(io.BytesIO(response.content))
        self.assertEqual(
            len(pdf_reader.pages), 1,
            "Consolidação não deve duplicar slides de setores com múltiplos envios"
        )

