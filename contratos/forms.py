from datetime import date
from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.utils.safestring import mark_safe
from .models import Empresa, Contrato, Agente, Integrante, Comissao

class EstiloFormMixin:
    """Mixin para aplicar estilos Bootstrap aos campos"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'

class EmpresaForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ['razao_social', 'cnpj', 'contato']
        help_texts = {
            'cnpj': 'Apenas números ou formato padrão xx.xxx.xxx/0001-xx',
            'contato': 'Nome do representante, telefone ou e-mail principal'
        }

class ContratoForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Contrato
        fields = ['numero', 'empresa', 'objeto', 'vigencia_inicio', 'vigencia_fim', 'valor_total']
        widgets = {
            'vigencia_inicio': forms.DateInput(attrs={'type': 'date'}),
            'vigencia_fim': forms.DateInput(attrs={'type': 'date'}),
            'objeto': forms.Textarea(attrs={'rows': 4}),
        }

class AgenteForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Agente
        fields = ['nome_completo', 'nome_de_guerra', 'posto', 'saram', 'cpf', 'data_ultimo_curso']
        widgets = {
            'data_ultimo_curso': forms.DateInput(attrs={'type': 'date'}),
        }

class ComissaoForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Comissao
        fields = ['contrato', 'tipo', 'portaria_numero', 'portaria_data', 'boletim_numero', 'boletim_data', 'data_inicio', 'data_fim', 'ativa']
        widgets = {
            'portaria_data': forms.DateInput(attrs={'type': 'date'}),
            'boletim_data': forms.DateInput(attrs={'type': 'date'}),
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contrato'].label_from_instance = lambda obj: f"{obj.numero} - {obj.empresa.razao_social}"

class IntegranteForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Integrante
        fields = ['comissao', 'agente', 'funcao', 'data_inicio', 'data_fim', 'portaria_numero', 'portaria_data', 'boletim_numero', 'boletim_data']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'type': 'date'}),
            'portaria_data': forms.DateInput(attrs={'type': 'date'}),
            'boletim_data': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra apenas comissões ativas e contratos vigentes para facilitar
        self.fields['comissao'].queryset = Comissao.objects.filter(ativa=True, contrato__vigencia_fim__gte=date.today())
        # Customiza formato com datas para identificar validade
        self.fields['comissao'].label_from_instance = lambda obj: f"{obj.contrato.numero} ({obj.get_tipo_display()}) - Vigência: {obj.data_inicio or '?'} a {obj.data_fim or '?'}"
        
        # Customiza o label do Agente para facilitar a busca (SARAM - Posto Nome - Nome Completo)
        self.fields['agente'].label_from_instance = lambda obj: f"{obj.saram} - {obj.posto.sigla} {obj.nome_de_guerra} | {obj.nome_completo}"

    def clean(self):
        cleaned_data = super().clean()
        comissao = cleaned_data.get('comissao')
        data_inicio = cleaned_data.get('data_inicio')
        data_fim = cleaned_data.get('data_fim')

        if comissao and data_inicio:
            # Valida início
            if comissao.data_inicio and data_inicio < comissao.data_inicio:
                self.add_error('data_inicio', f"A data de início não pode ser anterior ao início da comissão ({comissao.data_inicio.strftime('%d/%m/%Y')}).")
            
            # Valida fim
            if data_fim and comissao.data_fim and data_fim > comissao.data_fim:
                 self.add_error('data_fim', f"A data de término não pode ultrapassar o fim da comissão ({comissao.data_fim.strftime('%d/%m/%Y')}).")
            
            # Valida fim da comissão se não houver data fim (opcional, dependendo da regra)
            if not data_fim and comissao.data_fim:
                 # Se a designação for permanente até o fim, ok, mas se tiver validade...
                 pass
        
        return cleaned_data


class AlterarSenhaForm(EstiloFormMixin, DjangoPasswordChangeForm):
    """Formulário de alteração de senha em português"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Traduz labels para português
        self.fields['old_password'].label = 'Senha atual'
        self.fields['new_password1'].label = 'Nova senha'
        self.fields['new_password2'].label = 'Confirmação da nova senha'
        
        # Traduz help texts para português
        self.fields['new_password1'].help_text = mark_safe('''
            <ul class="mb-0">
                <li>Sua senha não pode ser muito parecida com suas outras informações pessoais.</li>
                <li>Sua senha deve conter pelo menos 8 caracteres.</li>
                <li>Sua senha não pode ser uma senha comumente usada.</li>
                <li>Sua senha não pode ser inteiramente numérica.</li>
            </ul>
        ''')
        self.fields['new_password2'].help_text = 'Digite a mesma senha novamente, para verificação.'
        
        # Remove help text da senha antiga
        self.fields['old_password'].help_text = None
