from datetime import date, timedelta
from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.utils.safestring import mark_safe
from .models import Empresa, Contrato, Agente, Integrante, Comissao, ConfiguracaoSistema
from .utils import clean_digits, format_cpf, format_cnpj

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
    houve_substituicao = forms.TypedChoiceField(
        label="Houve substituição de fiscal?",
        coerce=lambda x: str(x).lower() in ['sim', 'true', 'on', '1'],
        choices=[('sim', 'Sim'), ('nao', 'Não')],
        widget=forms.RadioSelect,
        required=True
    )
    substituicao_entrega_formal = forms.ChoiceField(
        label="Entrega formal dos registros pelo substituto?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=False
    )
    confirmacao_siloms_assinatura = forms.TypedChoiceField(
        label="Prazos de assinatura/início atualizados no SILOMS?",
        coerce=lambda x: str(x).lower() in ['sim', 'true', 'on', '1'],
        choices=[('sim', 'Sim'), ('nao', 'Não')],
        widget=forms.RadioSelect,
        required=True
    )
    confirmacao_siloms_vigencia = forms.TypedChoiceField(
        label="Vigência (incluindo aditivos) correta no SILOMS?",
        coerce=lambda x: str(x).lower() in ['sim', 'true', 'on', '1'],
        choices=[('sim', 'Sim'), ('nao', 'Não')],
        widget=forms.RadioSelect,
        required=True
    )
    confirmacao_siloms_execucao = forms.ChoiceField(
        label="Data término da execução físico-financeira conferida no SILOMS?",
        choices=[('sim', 'Sim'), ('na', 'N/A')],
        widget=forms.RadioSelect,
        required=True
    )
    data_execucao_fisico_financeira = forms.DateField(
        label="Data do término da execução físico-financeira",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_data_execucao_fisico_financeira'}),
        required=False
    )
    possibilidade_aditivo = forms.ChoiceField(
        label="Contrato admite termo aditivo?",
        choices=[('sim', 'Sim'), ('na', 'Não há mais possibilidade/Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    tratativas_120_dias = forms.ChoiceField(
        label="Iniciadas tratativas 120 dias antes?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    coordenacao_doc_scon = forms.ChoiceField(
        label="Coordenada informação com DOC/SCON?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    garantia_vigente = forms.ChoiceField(
        label="Garantia contratual dentro da vigência?",
        choices=[('sim', 'Sim'), ('nao', 'Não (Vencida)'), ('na', 'Não se aplica / Sem garantia')],
        widget=forms.RadioSelect,
        required=True
    )
    cronograma_fisico_financeiro = forms.ChoiceField(
        label="Cumprimento do Cronograma Físico-Financeiro",
        choices=[('conforme', 'Conforme o previsto'), ('atrasado', 'Atrasado')],
        widget=forms.RadioSelect,
        required=True
    )
    alteracao_cronograma = forms.ChoiceField(
        label="Alteração no cronograma?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    atraso_entrega = forms.ChoiceField(
        label="Atraso na entrega?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    impossibilidade_recebimento = forms.ChoiceField(
        label="Impossibilidade de recebimento?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    diligencia_visita = forms.ChoiceField(
        label="Diligência/visita técnica?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    imr_aplicado = forms.ChoiceField(
        label="IMR aplicado?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    glosa_realizada = forms.ChoiceField(
        label="Glosa realizada?",
        choices=[('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')],
        widget=forms.RadioSelect,
        required=True
    )
    empresa_sancionada = forms.ChoiceField(
        label="Empresa sancionada com impedimento de licitar e contratar e/ou declaração de inidoneidade para licitar ou contratar?",
        choices=[('sim', 'Sim'), ('nao', 'Não')],
        widget=forms.RadioSelect,
        required=True
    )
    doc_sancao_siloms = forms.ChoiceField(
        label="Documentação comprobatória foi inserida no SILOMS?",
        choices=[('sim', 'Sim'), ('nao', 'Não')],
        widget=forms.RadioSelect,
        required=False
    )
    ocorrencias_ativas_empresa = forms.ChoiceField(
        label="Ocorrências ativas reincidentes?",
        choices=[('sim', 'Sim'), ('nao', 'Não')],
        widget=forms.RadioSelect,
        required=True
    )
    necessidade_paai = forms.ChoiceField(
        label="Necessidade de PAAI?",
        choices=[('sim', 'Sim'), ('nao', 'Não')],
        widget=forms.RadioSelect,
        required=True
    )

    class Meta:
        model = ControleExecucao
        fields = [
            'agente', 'mes_referencia', 'ano_referencia',
            # Seção 1
            'houve_substituicao', 'substituicao_entrega_formal', 'substituicao_obs',
            # Seção 2
            'confirmacao_siloms_assinatura', 'confirmacao_siloms_vigencia', 'confirmacao_siloms_execucao',
            'data_execucao_fisico_financeira',
            'possibilidade_aditivo', 'tratativas_120_dias', 'coordenacao_doc_scon',
            'garantia_vigente', 'garantia_providencias',
            # Seção 3
            'notas_empenho', 'obs_sem_empenho', 'cronograma_fisico_financeiro',
            # Seção 4
            'detalhamento_cronograma', 'alteracao_cronograma', 'alteracao_cronograma_desc',
            'atraso_entrega', 'atraso_entrega_desc', 'impossibilidade_recebimento', 'impossibilidade_recebimento_desc',
            'diligencia_visita', 'diligencia_visita_desc', 'imr_aplicado', 'glosa_realizada', 'glosa_desc',
            # Seção 5
            'relatorio_ocorrencias',
            # Seção 6
            'empresa_sancionada', 'doc_sancao_siloms', 'sancao_observacao',
            'ocorrencias_ativas_empresa', 'necessidade_paai', 'paai_justificativa',
            # Geral
            'observacao',
        ]
        widgets = {
            'mes_referencia': forms.HiddenInput(),
            'ano_referencia': forms.HiddenInput(),
            'garantia_providencias': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Relatar providências adotadas quanto à renovação ou execução da garantia...'}),
            'notas_empenho': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Ex: 2026NE000123, 2026NE000456'}),
            'obs_sem_empenho': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Detalhar gestões providenciadas no SILOMS...'}),
            'detalhamento_cronograma': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descreva brevemente o status da execução...'}),
            'alteracao_cronograma_desc': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Descrever ações do fiscal...'}),
            'atraso_entrega_desc': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Descrever ações do fiscal...'}),
            'impossibilidade_recebimento_desc': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Descrever ações do fiscal...'}),
            'diligencia_visita_desc': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Detalhar resultados obtidos e ações...'}),
            'glosa_desc': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Detalhar ações fiscais e valores glosados...'}),
            'relatorio_ocorrencias': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Será preenchido pelo assistente de ocorrências...'}),
            'sancao_observacao': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Observações / Detalhamento da Sanção...'}),
            'paai_justificativa': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Detalhar infrações e ofício ao Ordenador de Despesas...'}),
            'substituicao_obs': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Observações sobre a transição de fiscal...'}),
            'observacao': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observações gerais...'}),
        }

    def __init__(self, *args, **kwargs):
        contrato = kwargs.pop('contrato', None)
        dentro_prazo_aditivo = kwargs.pop('dentro_prazo_aditivo', True)
        self.dentro_prazo_aditivo = dentro_prazo_aditivo
        super().__init__(*args, **kwargs)

        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        mes_prev = ultimo_dia_mes_anterior.month
        ano_prev = ultimo_dia_mes_anterior.year

        self.fields['mes_referencia'].initial = mes_prev
        self.fields['ano_referencia'].initial = ano_prev

        if not dentro_prazo_aditivo:
            self.fields['possibilidade_aditivo'].required = False
            self.fields['tratativas_120_dias'].required = False
            self.fields['coordenacao_doc_scon'].required = False
            self.initial['possibilidade_aditivo'] = 'na'
            self.initial['tratativas_120_dias'] = 'na'
            self.initial['coordenacao_doc_scon'] = 'na'

        if self.instance and self.instance.pk:
            self.initial['houve_substituicao'] = 'sim' if self.instance.houve_substituicao else 'nao'
            self.initial['substituicao_entrega_formal'] = self.instance.substituicao_entrega_formal or ''
            self.initial['confirmacao_siloms_assinatura'] = 'sim' if self.instance.confirmacao_siloms_assinatura else 'nao'
            self.initial['confirmacao_siloms_vigencia'] = 'sim' if self.instance.confirmacao_siloms_vigencia else 'nao'
            self.initial['confirmacao_siloms_execucao'] = self.instance.confirmacao_siloms_execucao or ''
            self.initial['possibilidade_aditivo'] = self.instance.possibilidade_aditivo or ('na' if not dentro_prazo_aditivo else '')
            self.initial['tratativas_120_dias'] = self.instance.tratativas_120_dias or ('na' if not dentro_prazo_aditivo else '')
            self.initial['coordenacao_doc_scon'] = self.instance.coordenacao_doc_scon or ('na' if not dentro_prazo_aditivo else '')
            self.initial['garantia_vigente'] = self.instance.garantia_vigente or ''
            self.initial['cronograma_fisico_financeiro'] = self.instance.cronograma_fisico_financeiro or ''
            self.initial['alteracao_cronograma'] = self.instance.alteracao_cronograma or ''
            self.initial['atraso_entrega'] = self.instance.atraso_entrega or ''
            self.initial['impossibilidade_recebimento'] = self.instance.impossibilidade_recebimento or ''
            self.initial['diligencia_visita'] = self.instance.diligencia_visita or ''
            self.initial['imr_aplicado'] = self.instance.imr_aplicado or ''
            self.initial['glosa_realizada'] = self.instance.glosa_realizada or ''
            self.initial['empresa_sancionada'] = self.instance.empresa_sancionada or ''
            self.initial['doc_sancao_siloms'] = self.instance.doc_sancao_siloms or ''
            self.initial['ocorrencias_ativas_empresa'] = self.instance.ocorrencias_ativas_empresa or ''
            self.initial['necessidade_paai'] = self.instance.necessidade_paai or ''

        if contrato:
            agentes_ids = Integrante.objects.filter(
                comissao__contrato=contrato,
                comissao__ativa=True,
                comissao__tipo='FISCALIZACAO',
                data_desligamento__isnull=True
            ).values_list('agente_id', flat=True).distinct()
            self.fields['agente'].queryset = Agente.objects.filter(id__in=agentes_ids).select_related('posto')
            self.fields['agente'].empty_label = "Selecione o Fiscal..."

    def clean(self):
        cleaned_data = super().clean()

        if not getattr(self, 'dentro_prazo_aditivo', True):
            cleaned_data['possibilidade_aditivo'] = 'na'
            cleaned_data['tratativas_120_dias'] = 'na'
            cleaned_data['coordenacao_doc_scon'] = 'na'

        siloms_exec = cleaned_data.get('confirmacao_siloms_execucao')
        dt_exec = cleaned_data.get('data_execucao_fisico_financeira')
        houve_sub = cleaned_data.get('houve_substituicao')
        sub_entrega = cleaned_data.get('substituicao_entrega_formal')
        emp_sancionada = cleaned_data.get('empresa_sancionada')
        doc_siloms = cleaned_data.get('doc_sancao_siloms')

        if siloms_exec == 'sim' and not dt_exec:
            self.add_error('data_execucao_fisico_financeira', 'Informe a data do término da execução físico-financeira ao marcar Sim.')
        elif siloms_exec != 'sim':
            cleaned_data['data_execucao_fisico_financeira'] = None

        if houve_sub and not sub_entrega:
            self.add_error('substituicao_entrega_formal', 'Informe se houve entrega formal dos registros pelo substituto.')

        if emp_sancionada == 'sim' and not doc_siloms:
            self.add_error('doc_sancao_siloms', 'Este campo é obrigatório.')
        elif emp_sancionada != 'sim':
            cleaned_data['doc_sancao_siloms'] = None
            cleaned_data['sancao_observacao'] = ''

        return cleaned_data


class RegistroFaturaForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = RegistroFatura
        fields = ['numero_nf', 'valor', 'numero_ob']


class OcorrenciaContratualForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = OcorrenciaContratual
        fields = ['data', 'tipo', 'descricao', 'acao_fiscal', 'prazo']
        widgets = {
            'data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 2}),
            'acao_fiscal': forms.Textarea(attrs={'rows': 2}),
        }

