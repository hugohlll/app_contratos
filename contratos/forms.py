from datetime import date
from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.utils.safestring import mark_safe
from .models import Empresa, Contrato, Agente, Integrante, Comissao
from .utils import clean_digits, format_cpf, format_cnpj

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
        fields = ['razao_social', 'cnpj']
        help_texts = {
            'cnpj': 'Apenas números ou formato padrão xx.xxx.xxx/0001-xx',
        }

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get('cnpj')
        digits = clean_digits(cnpj)
        
        # Se o usuário tentar apagar no update, o model dirá que é required (unique=True geralmente implica required no form a menos que blank=True)
        # O model diz: unique=True, mas não blank=True. Então é obrigatório.
        
        if len(digits) != 14:
            raise forms.ValidationError("O CNPJ deve conter exatamente 14 números.")
            
        return format_cnpj(digits)



class ContratoForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Contrato
        fields = ['tipo', 'numero', 'pag', 'empresa', 'objeto', 'vigencia_inicio', 'vigencia_fim', 'valor_total']
        widgets = {
            'vigencia_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'vigencia_fim': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'objeto': forms.Textarea(attrs={'rows': 4}),
        }

class AgenteForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Agente
        fields = ['nome_completo', 'nome_de_guerra', 'posto', 'saram', 'cpf', 'data_ultimo_curso']
        widgets = {
            'data_ultimo_curso': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if not cpf:
            return cpf
            
        digits = clean_digits(cpf)
        if len(digits) != 11:
            raise forms.ValidationError("O CPF deve conter exatamente 11 números.")
            
        return format_cpf(digits)

class ComissaoForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Comissao
        fields = ['contrato', 'tipo', 'portaria_numero', 'portaria_data', 'boletim_numero', 'boletim_data', 'data_inicio', 'data_fim', 'ativa']
        widgets = {
            'portaria_data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'boletim_data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contrato'].label_from_instance = lambda obj: f"{obj.numero} - {obj.empresa.razao_social}"

    def clean(self):
        cleaned_data = super().clean()
        contrato = cleaned_data.get('contrato')
        tipo_comissao = cleaned_data.get('tipo')

        if contrato and tipo_comissao:
            # Regra: Contratos de RECEITA não podem ter comissão de RECEBIMENTO
            if contrato.tipo == 'RECEITA' and tipo_comissao == 'RECEBIMENTO':
                # Adiciona erro ao campo 'tipo' e também erro geral se desejar
                self.add_error('tipo', "Contratos de RECEITA não possuem comissão de Recebimento, apenas de Fiscalização.")
        
        # Validação de Data Fim para Comissões Ativas
        data_fim = cleaned_data.get('data_fim')
        ativa = cleaned_data.get('ativa')
        
        if ativa and data_fim:
            if data_fim < date.today():
                self.add_error('data_fim', "Uma comissão ativa não pode ter data de término anterior à data atual.")
        
        # Impedir duas comissões ativas do mesmo tipo para o mesmo contrato
        if contrato and tipo_comissao and ativa:
            qs = Comissao.objects.filter(contrato=contrato, tipo=tipo_comissao, ativa=True)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                tipo_display = dict(Comissao.TIPO_CHOICES).get(tipo_comissao, tipo_comissao)
                self.add_error('ativa', f"Já existe uma comissão de {tipo_display} ativa para o contrato {contrato}. "
                               f"Desative a comissão existente antes de ativar uma nova.")
        
        return cleaned_data

class IntegranteForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Integrante
        fields = ['comissao', 'agente', 'funcao', 'data_inicio', 'data_fim', 'portaria_numero', 'portaria_data', 'boletim_numero', 'boletim_data']
        widgets = {
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'portaria_data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'boletim_data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra apenas comissões ativas e contratos vigentes para facilitar
        qs = Comissao.objects.filter(ativa=True, contrato__vigencia_fim__gte=date.today())
        
        # Garante que a comissão atual (mesmo inativa ou vencida) esteja no queryset
        comissao_id = None
        
        if hasattr(self, 'instance') and self.instance and hasattr(self.instance, 'comissao_id') and self.instance.comissao_id:
            comissao_id = self.instance.comissao_id
        elif hasattr(self, 'initial') and self.initial and self.initial.get('comissao'):
            comp = self.initial['comissao']
            comissao_id = comp.id if hasattr(comp, 'id') else comp
        elif hasattr(self, 'data') and self.data and self.data.get('comissao'):
            comissao_id = self.data.get('comissao')
            
        if comissao_id:
            qs = qs | Comissao.objects.filter(id=comissao_id)
            
        self.fields['comissao'].queryset = qs.distinct()
        
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
