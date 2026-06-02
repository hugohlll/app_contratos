"""
Tests para validar que os dropdowns Select2 nas páginas de prestação de contas
carregam corretamente (CSS fora de <style>, JS presente, selects renderizados).

Regressão: o bloco {% block extra_css %} estava dentro de uma tag <style>,
fazendo com que as tags <link> do Select2 fossem ignoradas pelo navegador.
"""
import re
from django.test import TestCase, Client
from django.urls import reverse
from contratos.models import Contrato, Empresa, Setor
from datetime import date, timedelta


class Select2FiscaisPageTest(TestCase):
    """Testes para a página /prestacoes/fiscais/ (seleção de contrato)."""

    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Select2 Test",
            cnpj="11.111.111/0001-11"
        )
        self.contrato = Contrato.objects.create(
            numero="001/2025",
            objeto="Contrato para teste de Select2",
            tipo="DESPESA",
            empresa=self.empresa,
            vigencia_inicio=date.today() - timedelta(days=30),
            vigencia_fim=date.today() + timedelta(days=335),
            valor_total=50000.00
        )

    def test_page_returns_200(self):
        """A página de seleção de fiscais deve retornar HTTP 200."""
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        self.assertEqual(response.status_code, 200)

    def test_select2_css_outside_style_tag(self):
        """O CSS do Select2 deve estar fora de tags <style> (como <link> no <head>)."""
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        content = response.content.decode('utf-8')

        # Verifica que o link do Select2 CSS existe no HTML
        self.assertIn('select2@4.1.0-rc.0/dist/css/select2.min.css', content)
        self.assertIn('select2-bootstrap-5-theme', content)

        # Verifica que as tags <link> do Select2 NÃO estão dentro de <style>...</style>
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
        for block in style_blocks:
            self.assertNotIn('select2', block.lower(),
                             "Tag <link> do Select2 encontrada dentro de <style>! "
                             "Isso causa falha no carregamento do CSS.")

    def test_select2_js_loaded(self):
        """O script do Select2 deve estar presente na página."""
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        content = response.content.decode('utf-8')
        self.assertIn('select2@4.1.0-rc.0/dist/js/select2.min.js', content)

    def test_select_element_present(self):
        """O <select> com id='contrato_select' deve estar presente."""
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        self.assertContains(response, 'id="contrato_select"')

    def test_contratos_in_select_options(self):
        """Os contratos vigentes devem aparecer como opções no <select>."""
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        content = response.content.decode('utf-8')
        self.assertIn('001/2025', content)
        self.assertIn('Empresa Select2 Test', content)

    def test_select2_initialization_script(self):
        """O script de inicialização do Select2 deve configurar o tema bootstrap-5."""
        response = self.client.get(reverse('portal_prestacao_fiscais'))
        content = response.content.decode('utf-8')
        self.assertIn("$('#contrato_select').select2(", content)
        self.assertIn("theme: 'bootstrap-5'", content)


class Select2GestoresPageTest(TestCase):
    """Testes para a página /prestacoes/gestores/ (seleção de setor)."""

    def setUp(self):
        self.client = Client()
        self.setor = Setor.objects.create(
            nome="Setor de Teste Select2",
            sigla="STS2"
        )

    def test_page_returns_200(self):
        """A página de seleção de gestores deve retornar HTTP 200."""
        response = self.client.get(reverse('portal_prestacao_gestores'))
        self.assertEqual(response.status_code, 200)

    def test_select2_css_outside_style_tag(self):
        """O CSS do Select2 deve estar fora de tags <style> (como <link> no <head>)."""
        response = self.client.get(reverse('portal_prestacao_gestores'))
        content = response.content.decode('utf-8')

        # Verifica que o link do Select2 CSS existe no HTML
        self.assertIn('select2@4.1.0-rc.0/dist/css/select2.min.css', content)
        self.assertIn('select2-bootstrap-5-theme', content)

        # Verifica que as tags <link> do Select2 NÃO estão dentro de <style>...</style>
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
        for block in style_blocks:
            self.assertNotIn('select2', block.lower(),
                             "Tag <link> do Select2 encontrada dentro de <style>! "
                             "Isso causa falha no carregamento do CSS.")

    def test_select2_js_loaded(self):
        """O script do Select2 deve estar presente na página."""
        response = self.client.get(reverse('portal_prestacao_gestores'))
        content = response.content.decode('utf-8')
        self.assertIn('select2@4.1.0-rc.0/dist/js/select2.min.js', content)

    def test_select_element_present(self):
        """O <select> com id='setor_select' deve estar presente."""
        response = self.client.get(reverse('portal_prestacao_gestores'))
        self.assertContains(response, 'id="setor_select"')

    def test_setores_in_select_options(self):
        """Os setores devem aparecer como opções no <select>."""
        response = self.client.get(reverse('portal_prestacao_gestores'))
        content = response.content.decode('utf-8')
        self.assertIn('STS2', content)
        self.assertIn('Setor de Teste Select2', content)

    def test_select2_initialization_script(self):
        """O script de inicialização do Select2 deve configurar o tema bootstrap-5."""
        response = self.client.get(reverse('portal_prestacao_gestores'))
        content = response.content.decode('utf-8')
        self.assertIn("$('#setor_select').select2(", content)
        self.assertIn("theme: 'bootstrap-5'", content)
