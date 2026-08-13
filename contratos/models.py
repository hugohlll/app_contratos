from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from datetime import date, timedelta


class PostoGraduacao(models.Model):
    sigla = models.CharField("Sigla", max_length=10, unique=True)
    descricao = models.CharField("Descrição Completa", max_length=100)
    senioridade = models.IntegerField("Ordem de Antiguidade", default=0)

    def __str__(self):
        return self.sigla

    class Meta:
        verbose_name = "Posto/Graduação"
        verbose_name_plural = "Postos e Graduações"
        ordering = ['senioridade']


# Período de validade da qualificação dos agentes (em dias)
DIAS_VALIDADE_QUALIFICACAO = 1825  # 5 anos


class Agente(models.Model):
    nome_completo = models.CharField("Nome Completo", max_length=150)
    nome_de_guerra = models.CharField("Nome de Guerra", max_length=50)
    posto = models.ForeignKey(PostoGraduacao, on_delete=models.PROTECT, verbose_name="Posto Atual")
    saram = models.CharField("SARAM/Matrícula", max_length=20, unique=True)
    cpf = models.CharField("CPF", max_length=14, blank=True, null=True)
    email = models.EmailField("E-mail", max_length=254, blank=True, null=True)
    ordem_manual = models.FloatField("Ordem Manual", default=0.0)

    data_ultimo_curso = models.DateField(null=True, blank=True, verbose_name="Data do Último Curso de Gestão")

    def __str__(self):
        return f"{self.posto.sigla} {self.nome_de_guerra}"

    @property
    def qualificacao_vencida(self):
        if not self.data_ultimo_curso: return True
        return date.today() > (self.data_ultimo_curso + timedelta(days=DIAS_VALIDADE_QUALIFICACAO))

    @property
    def data_validade_curso(self):
        if self.data_ultimo_curso: return self.data_ultimo_curso + timedelta(days=DIAS_VALIDADE_QUALIFICACAO)
        return None

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"


class Empresa(models.Model):
    razao_social = models.CharField("Razão Social", max_length=200)
    nome_fantasia = models.CharField("Nome Fantasia", max_length=200, blank=True, null=True)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)

    def __str__(self):
        return f"{self.nome_exibicao} ({self.cnpj})"

    @property
    def nome_exibicao(self):
        return self.nome_fantasia if self.nome_fantasia else self.razao_social

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"


class Funcao(models.Model):
    titulo = models.CharField("Título da Função", max_length=100, unique=True)
    sigla = models.CharField("Sigla", max_length=20, blank=True, null=True)
    ordem = models.IntegerField("Ordem de Hierarquia", default=0)
    ativa = models.BooleanField("Ativa?", default=True)

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Tipo de Função"
        verbose_name_plural = "Tipos de Função"
        ordering = ['ordem', 'titulo']


class Contrato(models.Model):
    TIPO_CHOICES = [
        ('RECEITA', 'Receita'),
        ('DESPESA', 'Despesa'),
    ]
    numero = models.CharField("Número do Contrato", max_length=20, unique=True)
    pag = models.CharField("Processo Administrativo de Gestão (PAG)", max_length=50, blank=True, null=True)
    tipo = models.CharField("Tipo", max_length=10, choices=TIPO_CHOICES, default='DESPESA')
    objeto = models.TextField("Objeto do Contrato")
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, verbose_name="Empresa Contratada")
    vigencia_inicio = models.DateField("Início da Vigência")
    vigencia_fim = models.DateField("Fim da Vigência")
    valor_total = models.DecimalField("Valor Total", max_digits=12, decimal_places=2)

    @property
    def data_recomendada_aditivo(self):
        """Data recomendada para início das tratativas de aditivo (120 dias antes do término da vigência)"""
        if self.vigencia_fim:
            return self.vigencia_fim - timedelta(days=120)
        return None

    @property
    def data_limite_aditivo(self):
        """Data limite para o início das tratativas de aditivo (90 dias antes do término da vigência)"""
        if self.vigencia_fim:
            return self.vigencia_fim - timedelta(days=90)
        return None

    def __str__(self):
        return f"CT {self.numero} - {self.empresa.razao_social}"

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"




class Comissao(models.Model):
    CATEGORIA_CHOICES = [
        ('CONTRATO', 'Comissão de Contrato'),
        ('OUTRAS', 'Outras Comissões'),
    ]
    
    TIPO_CHOICES = [
        # Para contratos
        ('FISCALIZACAO', 'Fiscalização'),
        ('RECEBIMENTO', 'Recebimento de Contrato'),
        # Para outras (específicas)
        ('RECEBIMENTO_GERAL', 'Recebimento (geral)'),
        ('PLANEJAMENTO', 'Planejamento'),
        ('AVALIACAO', 'Avaliação'),
        ('EXAME', 'Exame'),
        ('LICITACAO', 'Licitação/Contratação'),
        ('DIVERSAS', 'Diversas'),
    ]

    categoria = models.CharField("Categoria", max_length=20, choices=CATEGORIA_CHOICES, default='CONTRATO')
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='comissoes', null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='FISCALIZACAO')
    descricao_objeto = models.TextField("Descrição/Objeto", blank=True, null=True)
    ativa = models.BooleanField(default=False)

    # --- CAMPOS DA PORTARIA DA COMISSÃO ---
    portaria_numero = models.CharField("Nº Portaria da Comissão", max_length=50, blank=True, null=True)
    portaria_data = models.DateField("Data da Portaria", blank=True, null=True)
    
    # --- CAMPOSTO DO BOLETIM DA COMISSÃO ---
    boletim_numero = models.CharField("Nº Boletim", max_length=50, blank=True, null=True)
    boletim_data = models.DateField("Data do Boletim", blank=True, null=True)
    
    # --- CÓDIGO SILOMS ---
    codigo_siloms = models.CharField(
        "Código SILOMS", 
        max_length=10, 
        blank=True, 
        null=True,
        validators=[RegexValidator(r'^\d{10}$', 'O código SILOMS deve conter exatamente 10 dígitos numéricos.')]
    )
    
    # VIGÊNCIA DA COMISSÃO (Global)
    data_inicio = models.DateField("Início da Comissão", blank=True, null=True)
    data_fim = models.DateField("Fim da Comissão", blank=True, null=True)

    def clean(self):
        if self.ativa and self.data_inicio and self.data_inicio > date.today():
            raise ValidationError(
                "Uma comissão não pode ser marcada como ativa com data de início futura "
                f"({self.data_inicio.strftime('%d/%m/%Y')}). "
                "Deixe-a inativa até que a data de início seja atingida."
            )
            
        if self.categoria == 'CONTRATO':
            if not self.contrato:
                raise ValidationError({'contrato': 'Para comissões de contrato, o contrato deve ser informado.'})
            if self.tipo not in ['FISCALIZACAO', 'RECEBIMENTO']:
                raise ValidationError({'tipo': 'Para comissões de contrato, o tipo deve ser Fiscalização ou Recebimento de Contrato.'})
            
        if self.categoria == 'OUTRAS':
            if not self.descricao_objeto:
                raise ValidationError({'descricao_objeto': 'A descrição ou objeto da comissão é obrigatória.'})
            if self.tipo in ['FISCALIZACAO', 'RECEBIMENTO']:
                raise ValidationError({'tipo': 'Para outras comissões, selecione um tipo específico (exceto os de contrato).'})

    def save(self, *args, **kwargs):
        # Autogeração da descrição para contratos
        if self.categoria == 'CONTRATO' and self.contrato:
            tipo_ct = self.contrato.get_tipo_display()
            self.descricao_objeto = f"Comissão de {self.get_tipo_display()} do Contrato de {tipo_ct} nº {self.contrato.numero} - {self.contrato.objeto}"
            
        super().save(*args, **kwargs)
        
        # Se a data fim da comissão mudar, precisamos garantir que as designações (integrantes)
        # não fiquem ativas além da nova data de término da comissão
        if self.data_fim:
            integrantes_afetados = self.integrantes.filter(data_fim__gt=self.data_fim)
            for integrante in integrantes_afetados:
                integrante.data_fim = self.data_fim
                # Usa update em vez de save para evitar o chamado do clean do integrante que poderia
                # falhar caso a data início fosse violada (isso será verificado no ComissaoForm)
                # O update não chama sinais ou o método save()
                Integrante.objects.filter(pk=integrante.pk).update(data_fim=self.data_fim)

    def __str__(self):
        if self.categoria == 'CONTRATO' and self.contrato:
            return f"Comissão de {self.get_tipo_display()} - {self.contrato.numero}"
        return f"Comissão de {self.get_tipo_display()}"

    class Meta:
        verbose_name = "Comissão"
        verbose_name_plural = "Comissões"
        ordering = ['tipo']  # FISCALIZACAO (F) vem antes de RECEBIMENTO (R)


class Integrante(models.Model):
    comissao = models.ForeignKey(Comissao, on_delete=models.CASCADE, related_name='integrantes')
    agente = models.ForeignKey(Agente, on_delete=models.PROTECT, verbose_name="Militar")
    funcao = models.ForeignKey(Funcao, on_delete=models.PROTECT, verbose_name="Função")

    # --- NOVO CAMPO: FOTO DO POSTO NA ÉPOCA ---
    posto_graduacao = models.ForeignKey(PostoGraduacao, on_delete=models.PROTECT, verbose_name="Posto na Época",
                                        null=True, blank=True)

    # DATAS DA DESIGNAÇÃO
    data_inicio = models.DateField("Início (Designação)")
    data_fim = models.DateField("Término Previsto", null=True, blank=True)

    # ENCERRAMENTO / DISPENSA
    data_desligamento = models.DateField("Data Efetiva de Saída", null=True, blank=True)
    motivo_desligamento = models.CharField("Motivo da Saída", max_length=100, blank=True, null=True)
    doc_desligamento = models.CharField("Doc. de Desligamento", max_length=50, blank=True, null=True)

    # DOCUMENTOS
    portaria_numero = models.CharField("Nº Portaria", max_length=50)
    portaria_data = models.DateField("Data da Portaria")

    boletim_numero = models.CharField("Nº Boletim", max_length=50, blank=True, null=True)
    boletim_data = models.DateField("Data do Boletim", blank=True, null=True)

    observacao = models.CharField("Obs", max_length=100, blank=True, null=True)
    
    # Campo para ordenação manual
    ordem = models.PositiveIntegerField("Ordem", default=0)

    # --- AUTOMATIZAÇÃO: SALVAR O POSTO ATUAL NO HISTÓRICO ---
    def save(self, *args, **kwargs):
        # Se for um novo registro ou se o posto estiver vazio, copia do Agente
        if not self.posto_graduacao and self.agente:
            self.posto_graduacao = self.agente.posto
            
        # Regra de Negócio: Auto-preenchimento de datas
        if not self.data_inicio and self.comissao.data_inicio:
            self.data_inicio = self.comissao.data_inicio
        if not self.data_fim and self.comissao.data_fim:
            self.data_fim = self.comissao.data_fim

        # Auto-incremento da ordem se for novo registro
        if not self.pk and self.ordem == 0:
            last_item = Integrante.objects.filter(comissao=self.comissao).order_by('-ordem').first()
            if last_item:
                self.ordem = last_item.ordem + 1
            else:
                self.ordem = 1
            
        super().save(*args, **kwargs)

    def clean(self):
        if self.data_fim and self.data_inicio > self.data_fim:
            raise ValidationError("A data de término previsto não pode ser anterior ao início.")
        if self.data_desligamento and self.data_inicio > self.data_desligamento:
            raise ValidationError("A data efetiva de saída não pode ser anterior ao início da designação.")
            
        comissao = getattr(self, 'comissao', None)
        if comissao:
            if comissao.data_inicio and self.data_inicio and self.data_inicio < comissao.data_inicio:
                raise ValidationError(f"A data de início da designação não pode ser anterior ao início da comissão ({comissao.data_inicio.strftime('%d/%m/%Y')}).")
            if comissao.data_fim and self.data_fim and self.data_fim > comissao.data_fim:
                raise ValidationError(f"A data de término da designação não pode ultrapassar o fim da comissão ({comissao.data_fim.strftime('%d/%m/%Y')}).")

    @property
    def is_ativo(self):
        hoje = date.today()
        if self.data_desligamento and self.data_desligamento <= hoje: return False
        if self.data_fim and self.data_fim < hoje: return False
        return True

    def __str__(self):
        # Agora usamos o posto histórico na representação
        posto_str = self.posto_graduacao.sigla if self.posto_graduacao else self.agente.posto.sigla
        status = "(ENCERRADO)" if not self.is_ativo else "(ATIVO)"
        return f"{posto_str} {self.agente.nome_de_guerra} - {self.funcao} {status}"

    class Meta:
        verbose_name = "Integrante"
        verbose_name_plural = "Histórico de Integrantes"
        ordering = ['ordem']


import re
from django.utils.text import slugify

def upload_prestacao_path(instance, filename):
    """
    Gera caminho: prestacoes/{posto}_{nome_guerra}_{empresa}_{contrato}_{mes_referencia}.pdf
    """
    posto = slugify(instance.agente.posto.sigla) if instance.agente and instance.agente.posto else "sem-posto"
    nome_guerra = slugify(instance.agente.nome_de_guerra) if instance.agente else "sem-nome"
    empresa = slugify(instance.contrato.empresa.razao_social)[:30] # Limitado a 30 chars
    contrato = instance.contrato.numero.replace('/', '-')
    
    nome = f"{posto}_{nome_guerra}_{empresa}_{contrato}_{instance.mes_referencia:02d}-{instance.ano_referencia}.pdf"
    
    # Limpa caracteres múltiplos indesejados
    nome = re.sub(r'_+', '_', nome)
    return f"prestacoes/{nome}"


class PrestacaoContas(models.Model):
    contrato = models.ForeignKey(
        Contrato, on_delete=models.CASCADE, related_name='prestacoes'
    )
    agente = models.ForeignKey(
        'Agente', on_delete=models.SET_NULL, null=True, verbose_name="Fiscal"
    )
    ano_referencia = models.IntegerField("Ano de Referência")
    mes_referencia = models.IntegerField("Mês de Referência")  # 1–12
    arquivo = models.FileField(
        "Arquivo PDF", upload_to=upload_prestacao_path, null=True, blank=True
    )
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('entregue', 'Entregue'),
        ('correcao', 'Aguardando Correção'),
        ('ok', 'Conformidade (OK!)'),
    ]
    status = models.CharField(
        "Status", max_length=15, choices=STATUS_CHOICES, default='entregue'
    )
    compor_apresentacao = models.BooleanField(
        "Compor Apresentação", default=False, help_text="Marque se este slide fará parte da apresentação consolidada"
    )
    data_envio = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta:
        verbose_name = "Prestação de Contas"
        verbose_name_plural = "Prestações de Contas"
        ordering = ['-ano_referencia', '-mes_referencia']

    def clean(self):
        hoje = date.today()
        if self.ano_referencia > hoje.year or (self.ano_referencia == hoje.year and self.mes_referencia >= hoje.month):
            raise ValidationError("Não é possível enviar uma prestação de contas para o mês atual ou meses futuros.")

    def __str__(self):
        return f"PC {self.contrato.numero} - {self.mes_referencia:02d}/{self.ano_referencia}"

class ApontamentoCorrecao(models.Model):
    prestacao = models.ForeignKey(
        PrestacaoContas, on_delete=models.CASCADE, related_name='apontamentos'
    )
    autor = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name="Registrado por"
    )
    descricao = models.TextField("Descrição das Inconsistências")
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apontamento de Correção"
        verbose_name_plural = "Apontamentos de Correção"
        ordering = ['-data_registro']

    def __str__(self):
        return f"Apontamento #{self.id} - {self.prestacao}"

class CalendarioPrestacao(models.Model):
    ano = models.IntegerField("Ano")
    mes = models.IntegerField("Mês")
    data_entrega = models.DateField("Data de Entrega dos Slides", null=True, blank=True)
    data_entrega_execucao = models.DateField("Data de Entrega do Livro do Fiscal", null=True, blank=True)
    data_apresentacao_fiscais = models.DateField("Data de Apresentação - Fiscais", null=True, blank=True)
    data_apresentacao_gestores = models.DateField("Data de Apresentação - Gestores", null=True, blank=True)

    class Meta:
        verbose_name = "Calendário de Prestação"
        verbose_name_plural = "Calendários de Prestação"
        ordering = ['ano', 'mes']
        unique_together = ['ano', 'mes']

    def __str__(self):
        return f"{self.mes:02d}/{self.ano}"


class Setor(models.Model):
    nome = models.CharField("Nome do Setor", max_length=150, unique=True)
    sigla = models.CharField("Sigla", max_length=20, blank=True, null=True)
    ordem = models.IntegerField("Ordem de Exibição", default=0)

    def __str__(self):
        if self.sigla:
            return f"{self.sigla} - {self.nome}"
        return self.nome

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        ordering = ['ordem', 'nome']


class CargoRegimental(models.Model):
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='cargos', verbose_name="Setor")
    agente = models.ForeignKey(Agente, on_delete=models.PROTECT, verbose_name="Gestor")
    cargo = models.CharField("Cargo/Função", max_length=100)
    boletim_numero = models.CharField("Nº do Boletim", max_length=50, blank=True, null=True)
    boletim_data = models.DateField("Data do Boletim", blank=True, null=True)
    ativo = models.BooleanField("Ativo?", default=True)
    observacao = models.CharField("Observação", max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.cargo} - {self.agente} ({self.setor})"

    class Meta:
        verbose_name = "Cargo Regimental"
        verbose_name_plural = "Cargos Regimentais"
        ordering = ['setor__ordem', 'setor__nome', 'cargo']


def upload_prestacao_setor_path(instance, filename):
    """
    Gera caminho: prestacoes_setor/{posto}_{nome_guerra}_{setor}_{mes_referencia}.pdf
    """
    posto = slugify(instance.agente.posto.sigla) if instance.agente and instance.agente.posto else "sem-posto"
    nome_guerra = slugify(instance.agente.nome_de_guerra) if instance.agente else "sem-nome"
    setor = slugify(instance.setor.nome)[:30] # Limitado a 30 chars
    
    nome = f"{posto}_{nome_guerra}_{setor}_{instance.mes_referencia:02d}-{instance.ano_referencia}.pdf"
    
    # Limpa caracteres múltiplos indesejados
    nome = re.sub(r'_+', '_', nome)
    return f"prestacoes_setor/{nome}"


class PrestacaoContasSetor(models.Model):
    setor = models.ForeignKey(
        Setor, on_delete=models.CASCADE, related_name='prestacoes_setor'
    )
    agente = models.ForeignKey(
        'Agente', on_delete=models.SET_NULL, null=True, verbose_name="Gestor do Setor"
    )
    ano_referencia = models.IntegerField("Ano de Referência")
    mes_referencia = models.IntegerField("Mês de Referência")  # 1–12
    arquivo = models.FileField(
        "Arquivo PDF", upload_to=upload_prestacao_setor_path, null=True, blank=True
    )
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('entregue', 'Entregue'),
        ('correcao', 'Aguardando Correção'),
        ('ok', 'Conformidade (OK!)'),
    ]
    status = models.CharField(
        "Status", max_length=15, choices=STATUS_CHOICES, default='entregue'
    )
    compor_apresentacao = models.BooleanField(
        "Compor Apresentação", default=False, help_text="Marque se este slide fará parte da apresentação consolidada"
    )
    data_envio = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta:
        verbose_name = "Prestação de Contas (Setor)"
        verbose_name_plural = "Prestações de Contas (Setores)"
        ordering = ['-ano_referencia', '-mes_referencia']

    def clean(self):
        hoje = date.today()
        if self.ano_referencia > hoje.year or (self.ano_referencia == hoje.year and self.mes_referencia >= hoje.month):
            raise ValidationError("Não é possível enviar uma prestação de contas para o mês atual ou meses futuros.")

    def __str__(self):
        return f"PC {self.setor.sigla or self.setor.nome} - {self.mes_referencia:02d}/{self.ano_referencia}"


class ApontamentoCorrecaoSetor(models.Model):
    prestacao = models.ForeignKey(
        PrestacaoContasSetor, on_delete=models.CASCADE, related_name='apontamentos'
    )
    autor = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name="Registrado por"
    )
    descricao = models.TextField("Descrição das Inconsistências")
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apontamento de Correção (Setor)"
        verbose_name_plural = "Apontamentos de Correção (Setores)"
        ordering = ['-data_registro']

    def __str__(self):
        return f"Apontamento #{self.id} - {self.prestacao}"


class ConfiguracaoSistema(models.Model):
    PERIODICIDADE_CHOICES = [
        ('diario', 'Diário'),
        ('semanal', 'Semanal'),
        ('mensal', 'Mensal'),
    ]

    backup_periodicidade = models.CharField(
        max_length=20,
        choices=PERIODICIDADE_CHOICES,
        default='diario',
        verbose_name="Periodicidade do Backup",
        help_text="Frequência com que o backup automatizado será executado."
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(ConfiguracaoSistema, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_config(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Configurações Gerais"


def upload_slide_avulso_path(instance, filename):
    """
    Gera caminho: slides_avulsos/{tipo}/{ano}/{mes}/{nome_limpo}.pdf
    """
    nome_limpo = slugify(instance.nome_slide)[:30]
    return f"slides_avulsos/{instance.tipo_apresentacao}/{instance.ano_referencia}/{instance.mes_referencia:02d}/{nome_limpo}.pdf"


class SlideApresentacao(models.Model):
    TIPO_CHOICES = [
        ('fiscais', 'Fiscais'),
        ('gestores', 'Gestores'),
    ]
    tipo_apresentacao = models.CharField("Tipo de Apresentação", max_length=15, choices=TIPO_CHOICES)
    ano_referencia = models.IntegerField("Ano de Referência")
    mes_referencia = models.IntegerField("Mês de Referência")
    nome_slide = models.CharField("Nome do Slide", max_length=100)
    arquivo = models.FileField("Arquivo PDF", upload_to=upload_slide_avulso_path)
    indice_posicao = models.FloatField("Posição na Apresentação", default=999.0, help_text="Define a ordem do slide na apresentação (menor valor aparece antes).")
    data_registro = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name="Enviado por")

    class Meta:
        verbose_name = "Slide Avulso"
        verbose_name_plural = "Slides Avulsos"
        ordering = ['indice_posicao', 'data_registro']

    def __str__(self):
        return f"Slide {self.nome_slide} ({self.get_tipo_apresentacao_display()}) - {self.mes_referencia:02d}/{self.ano_referencia}"


class ControleExecucao(models.Model):
    contrato = models.ForeignKey(
        Contrato, on_delete=models.CASCADE, related_name='controles_execucao'
    )
    agente = models.ForeignKey(
        Agente, on_delete=models.SET_NULL, null=True, verbose_name="Fiscal"
    )
    ano_referencia = models.IntegerField("Ano de Referência")
    mes_referencia = models.IntegerField("Mês de Referência")
    data_envio = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('entregue', 'Entregue'),
        ('correcao', 'Aguardando Correção'),
        ('ok', 'Conformidade (OK!)'),
    ]
    status = models.CharField(
        "Status", max_length=15, choices=STATUS_CHOICES, default='entregue'
    )

    SIM_NAO_NA = [('sim', 'Sim'), ('nao', 'Não'), ('na', 'Não se aplica')]
    SIM_NAO = [('sim', 'Sim'), ('nao', 'Não')]
    CONFORME_ATRASADO = [('conforme', 'Conforme o previsto'), ('atrasado', 'Atrasado')]

    # === Seção 2: Controle de Prazos e Marcos ===
    confirmacao_siloms_assinatura = models.BooleanField("Conferido com SILOMS (Assinatura)", default=False)
    confirmacao_siloms_vigencia = models.BooleanField("Conferido com SILOMS/Aditivo (Vigência)", default=False)
    confirmacao_siloms_execucao = models.CharField("Conferido com Cronograma/OS (Execução)", max_length=10, choices=SIM_NAO_NA, default='na')
    data_execucao_fisico_financeira = models.DateField("Data término da execução físico-financeira", null=True, blank=True)
    ADMITIR_ADITIVO_CHOICES = [
        ('sim', 'Sim'),
        ('na', 'Não há mais possibilidade/Não se aplica'),
        ('nao', 'Não há mais possibilidade/Não se aplica'),
    ]
    possibilidade_aditivo = models.CharField("Contrato admite termo aditivo?", max_length=10, choices=ADMITIR_ADITIVO_CHOICES, default='na')
    tratativas_120_dias = models.CharField("Iniciadas as tratativas para aditivação", max_length=5, choices=SIM_NAO_NA, default='na')
    coordenacao_doc_scon = models.CharField("Coordenada informação com DOC/SCON?", max_length=5, choices=SIM_NAO_NA, default='na')
    GARANTIA_CHOICES = [
        ('sim', 'Sim'),
        ('nao', 'Não (Vencida)'),
        ('na', 'Não se aplica / Sem garantia'),
    ]
    garantia_vigente = models.CharField("Garantia contratual dentro da vigência?", max_length=10, choices=GARANTIA_CHOICES, default='na')
    garantia_providencias = models.TextField("Providências adotadas (Garantia Vencida)", blank=True)

    # === Seção 3: Execução Orçamentária e Financeira ===
    notas_empenho = models.TextField("Notas de Empenho (com saldo)", blank=True)
    obs_sem_empenho = models.TextField("Obs. caso não haja empenho", blank=True)
    cronograma_fisico_financeiro = models.CharField("Cumprimento do Cronograma Físico-Financeiro", max_length=10, choices=CONFORME_ATRASADO, default='conforme')

    # === Seção 4: Cronograma e Medição de Resultados ===
    detalhamento_cronograma = models.TextField("Status do Cronograma de Execução", blank=True)
    alteracao_cronograma = models.BooleanField("Houve alteração em relação ao mês anterior?", default=False)
    alteracao_cronograma_desc = models.TextField("Ações do fiscal (Alteração Cronograma)", blank=True)
    atraso_entrega = models.BooleanField("Atraso na entrega dos produtos/serviços?", default=False)
    atraso_entrega_desc = models.TextField("Ações do fiscal (Atraso Entrega)", blank=True)
    impossibilidade_recebimento = models.BooleanField("Impossibilidade de recebimento?", default=False)
    impossibilidade_recebimento_desc = models.TextField("Ações do fiscal (Impossibilidade)", blank=True)
    diligencia_visita = models.BooleanField("Realização de diligência ou visita técnica?", default=False)
    diligencia_visita_desc = models.TextField("Resultados obtidos e ações (Diligência)", blank=True)

    imr_aplicado = models.CharField("Aplicado IMR?", max_length=5, choices=SIM_NAO, default='nao')
    glosa_realizada = models.BooleanField("Realizada glosa no período?", default=False)
    glosa_desc = models.TextField("Detalhamento de glosa e valores", blank=True)

    # === Seção 5: Ocorrências (Relatório Consolidado) ===
    relatorio_ocorrencias = models.TextField("Relatório de Ocorrências e Tratativas", blank=True)

    # === Seção 6: Apuração de Irregularidades (PAAI) ===
    ocorrencias_ativas_empresa = models.CharField("Ocorrências ativas por atraso/descumprimento reincidente?", max_length=5, choices=SIM_NAO, default='nao')
    necessidade_paai = models.CharField("Necessária solicitação de abertura de PAAI neste mês?", max_length=5, choices=SIM_NAO, default='nao')
    paai_justificativa = models.TextField("Detalhamento de infrações / Justificativa PAAI", blank=True)

    # === Controle de Substituição ===
    houve_substituicao = models.BooleanField("Houve substituição do fiscal/membro no período?", default=False)
    substituicao_entrega_formal = models.CharField("Entrega formal dos registros realizada pelo substituto?", max_length=5, choices=SIM_NAO_NA, default='na')
    substituicao_obs = models.TextField("Observações sobre a substituição", blank=True)

    # === Observações Gerais ===
    observacao = models.TextField("Observações Gerais", blank=True)

    class Meta:
        verbose_name = "Controle de Execução Contratual"
        verbose_name_plural = "Controles de Execução Contratual"
        ordering = ['-ano_referencia', '-mes_referencia']

    def __str__(self):
        return f"Controle Execução {self.contrato.numero} - {self.mes_referencia:02d}/{self.ano_referencia}"


class RegistroFatura(models.Model):
    controle = models.ForeignKey(
        ControleExecucao, on_delete=models.CASCADE, related_name='faturas'
    )
    numero_nf = models.CharField("Nº da Nota Fiscal / Fatura", max_length=50)
    valor = models.DecimalField("Valor (R$)", max_digits=14, decimal_places=2, default=0)
    numero_ob = models.CharField("Nº da Ordem Bancária (OB)", max_length=50, blank=True)

    class Meta:
        verbose_name = "Registro de Fatura"
        verbose_name_plural = "Registros de Faturas"

    def __str__(self):
        return f"NF {self.numero_nf} - R$ {self.valor}"


class OcorrenciaContratual(models.Model):
    controle = models.ForeignKey(
        ControleExecucao, on_delete=models.CASCADE, related_name='ocorrencias'
    )
    data = models.DateField("Data da Ocorrência")
    tipo = models.CharField("Tipo de Ocorrência", max_length=30, default='outro')
    descricao = models.TextField("Descrição da Ocorrência")
    acao_fiscal = models.TextField("Ação do Fiscal / Providência", blank=True)
    prazo = models.CharField("Prazo para Resolução", max_length=50, blank=True)

    class Meta:
        verbose_name = "Ocorrência Contratual"
        verbose_name_plural = "Ocorrências Contratuais"
        ordering = ['data']

    def __str__(self):
        return f"Ocorrência {self.tipo} - {self.data}"


class ApontamentoCorrecaoExecucao(models.Model):
    controle = models.ForeignKey(
        ControleExecucao, on_delete=models.CASCADE, related_name='apontamentos'
    )
    autor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    descricao = models.TextField("Descrição das Inconsistências")
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apontamento de Correção (Execução)"
        verbose_name_plural = "Apontamentos de Correção (Execução)"
        ordering = ['-data_registro']

    def __str__(self):
        return f"Apontamento #{self.id} - {self.controle}"
