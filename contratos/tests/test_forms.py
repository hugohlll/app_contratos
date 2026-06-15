from django.test import TestCase
from contratos.forms import ComissaoForm, EmpresaForm
from contratos.models import Contrato, Empresa, Comissao
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

    def _form_data(self, **overrides):
        """Helper para gerar dados base do formulário."""
        data = {
            'categoria': 'CONTRATO',
            'contrato': self.contrato.pk,
            'tipo': 'FISCALIZACAO',
            'portaria_numero': '123',
            'portaria_data': date.today(),
            'boletim_numero': '456',
            'boletim_data': date.today(),
            'data_inicio': date.today(),
            'data_fim': date.today() + timedelta(days=180),
            'ativa': True,
        }
        data.update(overrides)
        return data

    def test_clean_active_commission_past_end_date(self):
        """
        Testa se uma comissão ativa com data de fim no passado é inválida.
        """
        ontem = date.today() - timedelta(days=1)
        form = ComissaoForm(data=self._form_data(data_fim=ontem))
        self.assertFalse(form.is_valid(), "Comissão ativa com data fim no passado não deveria ser válida")
        self.assertIn('data_fim', form.errors)

    def test_reject_duplicate_active_commission_same_type_and_contract(self):
        """
        Testa se o sistema rejeita a criação de uma segunda comissão ativa
        do mesmo tipo para o mesmo contrato.
        """
        # Cria a primeira comissão ativa de FISCALIZACAO
        Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=180),
        )

        # Tenta criar uma segunda comissão ativa de FISCALIZACAO para o mesmo contrato
        form = ComissaoForm(data=self._form_data())
        self.assertFalse(form.is_valid(), "Não deveria permitir duas comissões ativas do mesmo tipo para o mesmo contrato")
        self.assertIn('ativa', form.errors)

    def test_allow_duplicate_inactive_commission(self):
        """
        Testa se o sistema permite criar uma comissão INATIVA quando já existe
        uma ativa do mesmo tipo para o mesmo contrato.
        """
        Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=180),
        )

        # Tenta criar uma segunda comissão INATIVA — deve ser permitido
        form = ComissaoForm(data=self._form_data(ativa=False))
        self.assertTrue(form.is_valid(), f"Deveria permitir comissão inativa duplicada: {form.errors}")

    def test_allow_different_type_active_commission(self):
        """
        Testa se o sistema permite criar uma comissão ativa de tipo diferente
        para o mesmo contrato.
        """
        Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=180),
        )

        # RECEBIMENTO ativo deve ser permitido quando FISCALIZACAO já está ativa
        form = ComissaoForm(data=self._form_data(tipo='RECEBIMENTO'))
        self.assertTrue(form.is_valid(), f"Deveria permitir comissão de tipo diferente: {form.errors}")

    def test_allow_edit_existing_active_commission(self):
        """
        Testa se editar a comissão ativa existente (mesma instância) não
        dispara o erro de duplicidade.
        """
        # Agora precisamos criar manualmente
        comissao = Comissao.objects.create(contrato=self.contrato, tipo='FISCALIZACAO', ativa=True)

        # Editar a mesma comissão deve ser permitido
        form = ComissaoForm(data=self._form_data(), instance=comissao)
        self.assertTrue(form.is_valid(), f"Deveria permitir editar a própria comissão ativa: {form.errors}")

    def test_categoria_outras_exige_descricao(self):
        """Testa se escolher a categoria OUTRAS exige a descricao_objeto e anula o contrato"""
        data = self._form_data(categoria='OUTRAS', tipo='RECEBIMENTO_GERAL', descricao_objeto='')
        form = ComissaoForm(data=data)
        self.assertFalse(form.is_valid())
        # O model.clean() lança erro para descricao_objeto vazio em categoria OUTRAS
        self.assertIn('descricao_objeto', form.errors)

    def test_categoria_outras_valida(self):
        """Testa se a categoria OUTRAS funciona corretamente quando tem descricao_objeto"""
        data = self._form_data(
            categoria='OUTRAS', 
            tipo='PLANEJAMENTO', 
            descricao_objeto='Equipe de Planejamento X',
            contrato=self.contrato.pk # enviando contrato para testar se o form.clean limpa ele
        )
        form = ComissaoForm(data=data)
        self.assertTrue(form.is_valid(), f"Deveria ser válido: {form.errors}")
        self.assertIsNone(form.cleaned_data['contrato'])

class EmpresaFormTest(TestCase):
    def test_empresa_form_has_nome_fantasia(self):
        form = EmpresaForm()
        self.assertIn('nome_fantasia', form.fields)

    def test_empresa_form_valid(self):
        data = {
            'razao_social': 'Empresa Teste LTDA',
            'nome_fantasia': 'Empresa Teste',
            'cnpj': '12.345.678/0001-90',
        }
        form = EmpresaForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        empresa = form.save()
        self.assertEqual(empresa.nome_fantasia, 'Empresa Teste')
        self.assertEqual(empresa.razao_social, 'Empresa Teste LTDA')

    def test_empresa_form_valid_without_nome_fantasia(self):
        data = {
            'razao_social': 'Empresa Teste LTDA',
            'nome_fantasia': '',
            'cnpj': '12.345.678/0001-90',
        }
        form = EmpresaForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        empresa = form.save()
        self.assertFalse(empresa.nome_fantasia)
