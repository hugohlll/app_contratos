from django.test import TestCase
from contratos.forms import ComissaoForm
from contratos.models import Contrato, Empresa
from datetime import date, timedelta

class ComissaoFormTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="12.345.678/0001-90")
        self.contrato = Contrato.objects.create(
            numero="001/2026",
            tipo="DESPESA",
            empresa=self.empresa,
            objeto="Objeto Teste",
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=10000.00
        )

    def test_clean_active_commission_past_end_date(self):
        """
        Testa se uma comissão ativa com data de fim no passado é inválida.
        """
        ontem = date.today() - timedelta(days=1)
        
        form_data = {
            'contrato': self.contrato.pk,
            'tipo': 'FISCALIZACAO',
            'portaria_numero': '123',
            'portaria_data': date.today(),
            'boletim_numero': '456',
            'boletim_data': date.today(),
            'data_inicio': date.today(),
            'data_fim': ontem,  # Data no passado
            'ativa': True       # Ativa
        }
        
        form = ComissaoForm(data=form_data)
        
        # O teste deve falhar aqui ANTES da correção, pois o form será válido
        # Após a correção, o form deve ser inválido
        self.assertFalse(form.is_valid(), "Comissão ativa com data fim no passado não deveria ser válida")
        self.assertIn('data_fim', form.errors)
