from django.db import models
from django.core.exceptions import ValidationError
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


class Agente(models.Model):
    nome_completo = models.CharField("Nome Completo", max_length=150)
    nome_de_guerra = models.CharField("Nome de Guerra", max_length=50)
    posto = models.ForeignKey(PostoGraduacao, on_delete=models.PROTECT, verbose_name="Posto Atual")
    saram = models.CharField("SARAM/Matrícula", max_length=20, unique=True)
    cpf = models.CharField("CPF", max_length=14, blank=True, null=True)

    data_ultimo_curso = models.DateField(null=True, blank=True, verbose_name="Data do Último Curso de Gestão")

    def __str__(self):
        return f"{self.posto.sigla} {self.nome_de_guerra}"

    @property
    def qualificacao_vencida(self):
        if not self.data_ultimo_curso: return True
        return date.today() > (self.data_ultimo_curso + timedelta(days=365))

    @property
    def data_validade_curso(self):
        if self.data_ultimo_curso: return self.data_ultimo_curso + timedelta(days=365)
        return None

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"


class Empresa(models.Model):
    razao_social = models.CharField("Razão Social", max_length=200)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

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
    tipo = models.CharField("Tipo", max_length=10, choices=TIPO_CHOICES, default='DESPESA')
    objeto = models.TextField("Objeto do Contrato")
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, verbose_name="Empresa Contratada")
    vigencia_inicio = models.DateField("Início da Vigência")
    vigencia_fim = models.DateField("Fim da Vigência")
    valor_total = models.DecimalField("Valor Total", max_digits=12, decimal_places=2)

    def __str__(self):
        return f"CT {self.numero} - {self.empresa.razao_social}"

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # Cria automaticamente uma comissão de fiscalização padrão
            Comissao.objects.create(contrato=self, tipo='FISCALIZACAO', ativa=True)


class Comissao(models.Model):
    TIPO_CHOICES = [
        ('FISCALIZACAO', 'Fiscalização'),
        ('RECEBIMENTO', 'Recebimento'),
    ]

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='comissoes')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='FISCALIZACAO')
    ativa = models.BooleanField(default=True)

    # --- CAMPOS DA PORTARIA DA COMISSÃO ---
    portaria_numero = models.CharField("Nº Portaria da Comissão", max_length=50, blank=True, null=True)
    portaria_data = models.DateField("Data da Portaria", blank=True, null=True)
    
    # --- CAMPOSTO DO BOLETIM DA COMISSÃO ---
    boletim_numero = models.CharField("Nº Boletim", max_length=50, blank=True, null=True)
    boletim_data = models.DateField("Data do Boletim", blank=True, null=True)
    
    # VIGÊNCIA DA COMISSÃO (Global)
    data_inicio = models.DateField("Início da Comissão", blank=True, null=True)
    data_fim = models.DateField("Fim da Comissão", blank=True, null=True)

    def __str__(self):
        return f"Comissão de {self.get_tipo_display()} - {self.contrato}"

    class Meta:
        verbose_name = "Comissão"
        verbose_name_plural = "Comissões"


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
            
        super().save(*args, **kwargs)

    def clean(self):
        if self.data_fim and self.data_inicio > self.data_fim:
            raise ValidationError("A data de término previsto não pode ser anterior ao início.")
        if self.data_desligamento and self.data_inicio > self.data_desligamento:
            raise ValidationError("A data efetiva de saída não pode ser anterior ao início da designação.")

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
        ordering = ['-data_inicio']