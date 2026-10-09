from datetime import date, timedelta
from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.utils.safestring import mark_safe
from .models import Empresa, Contrato, Agente, Integrante, Comissao, ConfiguracaoSistema
from .utils import clean_digits, format_cpf, format_cnpj, format_telefone
from contratos.services.execucao_modulos import ModulosLivroFiscalService

class EstiloFormMixin:
    """Mixin para aplicar estilos Bootstrap aos campos"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

class EmpresaForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ['razao_social', 'nome_fantasia', 'cnpj']
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
        fields = ['nome_completo', 'nome_de_guerra', 'posto', 'saram', 'cpf', 'email', 'data_ultimo_curso']
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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return email

        import re
        pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
        if not re.match(pattern, email):
            raise forms.ValidationError("Informe um e-mail válido no formato exemplo@dominio.com")

        return email

class ComissaoForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Comissao
        fields = ['categoria', 'contrato', 'tipo', 'descricao_objeto', 'codigo_siloms', 'portaria_numero', 'portaria_data', 'boletim_numero', 'boletim_data', 'data_inicio', 'data_fim', 'ativa']
        widgets = {
            'portaria_data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'boletim_data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'descricao_objeto': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contrato'].label_from_instance = lambda obj: f"{obj.numero} - {obj.empresa.razao_social}"
        self.fields['contrato'].required = False
        self.fields['descricao_objeto'].required = False

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')
        contrato = cleaned_data.get('contrato')
        tipo_comissao = cleaned_data.get('tipo')

        if categoria == 'OUTRAS':
            cleaned_data['contrato'] = None
            contrato = None

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
                
        # Validação: Impedir que a data_fim da comissão seja menor do que a data_inicio de algum integrante
        if self.instance and self.instance.pk and data_fim:
            integrantes_invalidos = self.instance.integrantes.filter(data_inicio__gt=data_fim)
            if integrantes_invalidos.exists():
                self.add_error('data_fim', "A data de término da comissão não pode ser anterior à data de início de algum integrante.")
        
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
        # Filtra apenas comissões ativas e contratos vigentes para facilitar,
        # e inclui também as comissões da categoria OUTRAS que não possuem contratos a vencer
        qs = Comissao.objects.filter(
            Q(ativa=True) & (
                Q(contrato__vigencia_fim__gte=date.today()) | 
                Q(categoria='OUTRAS')
            )
        )
        
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
        self.fields['comissao'].label_from_instance = lambda obj: f"{obj.contrato.numero if obj.contrato else obj.get_tipo_display()} ({obj.get_tipo_display()}) - Vigência: {obj.data_inicio or '?'} a {obj.data_fim or '?'}"
        
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
            
            # Valida fim (Não pode ser superior ao término da comissão)
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


from .models import PrestacaoContas
from django import forms
from datetime import date

class PrestacaoContasUploadForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = PrestacaoContas
        fields = ['agente', 'mes_referencia', 'ano_referencia', 'arquivo', 'observacao']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 2}),
            'mes_referencia': forms.HiddenInput(),
            'ano_referencia': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        contrato = kwargs.pop('contrato', None)
        super().__init__(*args, **kwargs)
        
        # Calcula o mês e ano anterior ao atual
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        mes_prev = ultimo_dia_mes_anterior.month
        ano_prev = ultimo_dia_mes_anterior.year
        
        self.fields['mes_referencia'].initial = mes_prev
        self.fields['ano_referencia'].initial = ano_prev
        
        # Filtra os agentes apenas para aqueles que compõem alguma comissão de fiscalização ativa deste contrato
        if contrato:
            agentes_ids = Integrante.objects.filter(
                comissao__contrato=contrato,
                comissao__ativa=True,
                comissao__tipo='FISCALIZACAO',
                data_desligamento__isnull=True
            ).values_list('agente_id', flat=True).distinct()
            self.fields['agente'].queryset = Agente.objects.filter(id__in=agentes_ids).select_related('posto')
            self.fields['agente'].empty_label = "Selecione o Fiscal..."

    def clean_arquivo(self):
        f = self.cleaned_data.get('arquivo')
        if not f:
            raise forms.ValidationError("Este campo é obrigatório. Envie um arquivo PDF.")
        if not f.name.lower().endswith('.pdf'):
            raise forms.ValidationError("Apenas arquivos PDF são aceitos.")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("O arquivo não pode exceder 10 MB.")
        return f


from .models import Setor, CargoRegimental

class SetorForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Setor
        fields = ['nome', 'sigla']

class CargoRegimentalForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = CargoRegimental
        fields = ['setor', 'agente', 'cargo', 'boletim_numero', 'boletim_data', 'ativo', 'observacao']
        widgets = {
            'boletim_data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['agente'].label_from_instance = lambda obj: f"{obj.posto.sigla} {obj.nome_de_guerra} | {obj.nome_completo}"


from .models import PrestacaoContasSetor

class PrestacaoContasSetorUploadForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = PrestacaoContasSetor
        fields = ['agente', 'mes_referencia', 'ano_referencia', 'arquivo', 'observacao']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 2}),
            'mes_referencia': forms.HiddenInput(),
            'ano_referencia': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        setor = kwargs.pop('setor', None)
        super().__init__(*args, **kwargs)
        
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        mes_prev = ultimo_dia_mes_anterior.month
        ano_prev = ultimo_dia_mes_anterior.year
        
        self.fields['mes_referencia'].initial = mes_prev
        self.fields['ano_referencia'].initial = ano_prev
        
        # Filtra os agentes apenas para aqueles que são chefes no setor selecionado
        if setor:
            agentes_ids = CargoRegimental.objects.filter(
                setor=setor,
                ativo=True
            ).values_list('agente_id', flat=True).distinct()
            self.fields['agente'].queryset = Agente.objects.filter(id__in=agentes_ids).select_related('posto')
            self.fields['agente'].empty_label = "Selecione o Gestor..."

    def clean_arquivo(self):
        f = self.cleaned_data.get('arquivo')
        if not f:
            raise forms.ValidationError("Este campo é obrigatório. Envie um arquivo PDF.")
        if not f.name.lower().endswith('.pdf'):
            raise forms.ValidationError("Apenas arquivos PDF são aceitos.")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("O arquivo não pode exceder 10 MB.")
        return f


class ConfiguracaoSistemaForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracaoSistema
        fields = ('backup_periodicidade',)


from .models import ControleExecucao, RegistroFatura, OcorrenciaContratual

class ControleExecucaoForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = ControleExecucao
        fields = [
            'agente', 'mes_referencia', 'ano_referencia', 'status',
            'omap', 'unidade_gestora',
            # Preposto da Contratada
            'preposto_nome', 'preposto_cargo', 'preposto_telefone', 'preposto_email',
            # Obras e Serviços de Engenharia (Anexo B)
            'eh_obra_engenharia', 'condicoes_climaticas', 'efetivo_trabalhadores', 'maquinario_equipamentos',
            'art_rrt', 'matricula_cei_cno', 'seguranca_trabalho_cat',
            # Ocorrências e Encerramento
            'sem_ocorrencias_periodo', 'relatorio_ocorrencias', 'observacao',
        ]
        widgets = {
            'mes_referencia': forms.HiddenInput(),
            'ano_referencia': forms.HiddenInput(),
            'status': forms.HiddenInput(),
            'omap': forms.HiddenInput(),
            'unidade_gestora': forms.HiddenInput(),
            'preposto_nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo do preposto'}),
            'preposto_cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cargo / Função na contratada'}),
            'preposto_telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(61) 99999-9999',
                'maxlength': '15',
                'inputmode': 'numeric',
            }),
            'preposto_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'preposto@empresa.com.br',
                'type': 'email',
                'autocomplete': 'email',
            }),
            'condicoes_climaticas': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Registro de chuvas, mau tempo e paralisações para fins de abono de dias...'}),
            'efetivo_trabalhadores': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Contagem de trabalhadores por função (pedreiros, serventes, engenheiros)...'}),
            'maquinario_equipamentos': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Relação de máquinas e equipamentos no canteiro e estado operacional...'}),
            'art_rrt': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº da ART/RRT quitada no CREA/CAU'}),
            'matricula_cei_cno': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº do CEI / CNO no INSS'}),
            'seguranca_trabalho_cat': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Uso de EPIs, registro de acidentes e comunicações (CAT)...'}),
            'relatorio_ocorrencias': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Resumo consolidado das ocorrências do período (opcional)...'}),
            'observacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Observações gerais, esclarecimentos ou apontamentos complementares...'}),
        }

    def __init__(self, *args, **kwargs):
        contrato = kwargs.pop('contrato', None)
        super().__init__(*args, **kwargs)

        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        mes_prev = ultimo_dia_mes_anterior.month
        ano_prev = ultimo_dia_mes_anterior.year

        if not self.initial.get('mes_referencia'):
            self.fields['mes_referencia'].initial = mes_prev
        if not self.initial.get('ano_referencia'):
            self.fields['ano_referencia'].initial = ano_prev
        if not self.initial.get('omap'):
            self.fields['omap'].initial = 'GAP-BR'
        if not self.initial.get('unidade_gestora'):
            self.fields['unidade_gestora'].initial = '120006 - GAP-BR'

        if 'status' in self.fields:
            self.fields['status'].required = False
        if 'omap' in self.fields:
            self.fields['omap'].required = False
        if 'unidade_gestora' in self.fields:
            self.fields['unidade_gestora'].required = False
        if 'preposto_telefone' in self.fields:
            self.fields['preposto_telefone'].widget.attrs['maxlength'] = '15'

        if contrato:
            agentes_ids = Integrante.objects.filter(
                comissao__contrato=contrato,
                comissao__ativa=True,
                comissao__tipo='FISCALIZACAO',
                data_desligamento__isnull=True
            ).values_list('agente_id', flat=True).distinct()
            self.fields['agente'].queryset = Agente.objects.filter(id__in=agentes_ids).select_related('posto')
            self.fields['agente'].empty_label = "Selecione o Fiscal..."

            # Preenchimento automático inteligente do Preposto a partir do mês anterior se campos vazios
            if not self.instance.pk or not self.instance.preposto_nome:
                ultimo_controle = ControleExecucao.objects.filter(
                    contrato=contrato
                ).exclude(preposto_nome='').order_by('-ano_referencia', '-mes_referencia').first()
                if ultimo_controle:
                    self.initial.setdefault('preposto_nome', ultimo_controle.preposto_nome)
                    self.initial.setdefault('preposto_cargo', ultimo_controle.preposto_cargo)
                    self.initial.setdefault('preposto_telefone', ultimo_controle.preposto_telefone)
                    self.initial.setdefault('preposto_email', ultimo_controle.preposto_email)

    def clean(self):
        cleaned_data = super().clean()
        # Se os campos modulares foram omitidos na submissão (bloco desativado no template),
        # preserva os valores originais da instância caso existam.
        if self.instance.pk and self.data:
            campos_modulares = [
                'preposto_nome', 'preposto_cargo', 'preposto_telefone', 'preposto_email',
                'eh_obra_engenharia', 'condicoes_climaticas', 'efetivo_trabalhadores',
                'maquinario_equipamentos', 'art_rrt', 'matricula_cei_cno', 'seguranca_trabalho_cat'
            ]
            for campo in campos_modulares:
                if campo not in self.data:
                    cleaned_data[campo] = getattr(self.instance, campo)
        return cleaned_data

    def clean_preposto_telefone(self):
        if self.data and 'preposto_telefone' not in self.data and self.instance.pk:
            return self.instance.preposto_telefone
        telefone = self.cleaned_data.get('preposto_telefone', '')
        if not telefone:
            return ''
        digits = clean_digits(telefone)
        if not digits:
            return ''
        if len(digits) != 11:
            raise ValidationError('O telefone celular deve conter exatamente 11 dígitos com DDD: (99) 99999-9999.')
        return format_telefone(digits)

    def clean_preposto_email(self):
        if self.data and 'preposto_email' not in self.data and self.instance.pk:
            return self.instance.preposto_email
        email = self.cleaned_data.get('preposto_email', '')
        if not email:
            return ''
        email = email.strip()
        import re
        pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
        if not re.match(pattern, email):
            raise ValidationError('Informe um e-mail válido no formato usuario@dominio.com.')
        return email.lower()


class RegistroFaturaForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = RegistroFatura
        fields = ['numero_nf', 'valor', 'numero_ob']


class OcorrenciaContratualForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = OcorrenciaContratual
        fields = [
            'data_hora', 'local', 'tipo', 'descricao', 'dispositivo_violado',
            'evidencias', 'notificacao_emitida', 'notificacao_numero',
            'prazo_dias_uteis', 'ciencia_preposto', 'tramite_arc',
            'status_ocorrencia', 'acao_fiscal'
        ]
        widgets = {
            'data_hora': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'local': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Instalações, setor, dependência'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Narrativa detalhada e factual do fato'}),
            'dispositivo_violado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cláusula contratual, item do TR ou edital'}),
            'evidencias': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Relatório fotográfico, documento SIGADAER, etc.'}),
            'notificacao_numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 001/GAP-BR/2026'}),
            'prazo_dias_uteis': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'ciencia_preposto': forms.Select(attrs={'class': 'form-select'}),
            'status_ocorrencia': forms.Select(attrs={'class': 'form-select'}),
            'acao_fiscal': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Providência / determinação imediata do fiscal'}),
        }


