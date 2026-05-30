from django.contrib import admin
from .models import PostoGraduacao, Agente, Empresa, Funcao, Contrato, Comissao, Integrante

@admin.register(PostoGraduacao)
class PostoGraduacaoAdmin(admin.ModelAdmin):
    list_display = ('sigla', 'descricao', 'senioridade')
    ordering = ('senioridade',)

@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    list_display = ('posto', 'nome_de_guerra', 'nome_completo', 'saram', 'email')
    search_fields = ('nome_completo', 'nome_de_guerra', 'saram', 'email')
    list_filter = ('posto',)

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('razao_social', 'cnpj')
    search_fields = ('razao_social', 'cnpj')

@admin.register(Funcao)
class FuncaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'sigla', 'ativa')
    search_fields = ('titulo', 'sigla')

# --- CONFIGURAÇÃO DA COMISSÃO ---

class IntegranteInline(admin.TabularInline):
    model = Integrante
    extra = 0
    autocomplete_fields = ['agente', 'funcao']
    # Mostra colunas resumidas na tela da Comissão, incluindo a data de saída efetiva
    fields = ('funcao', 'agente', 'data_inicio', 'data_fim', 'data_desligamento', 'portaria_numero')

@admin.register(Comissao)
class ComissaoAdmin(admin.ModelAdmin):
    list_display = ('get_tipo', 'contrato', 'ativa')
    list_filter = ('tipo', 'ativa')
    search_fields = ('contrato__numero',)
    inlines = [IntegranteInline]
    autocomplete_fields = ['contrato']

    def get_tipo(self, obj):
        return obj.get_tipo_display()
    get_tipo.short_description = "Tipo"

# --- HISTÓRICO DETALHADO (NOVO) ---
# Permite editar os detalhes de desligamento de forma organizada

@admin.register(Integrante)
class IntegranteAdmin(admin.ModelAdmin):
    list_display = ('agente', 'funcao', 'comissao', 'data_inicio', 'data_fim', 'data_desligamento', 'is_ativo_display')
    list_filter = ('funcao', 'comissao__contrato')
    search_fields = ('agente__nome_de_guerra', 'comissao__contrato__numero')
    autocomplete_fields = ['agente', 'funcao', 'comissao']

    # Organiza o formulário em secções
    fieldsets = (
        ('Dados da Designação', {
            'fields': ('comissao', 'agente', 'funcao', 'data_inicio', 'data_fim', 'portaria_numero', 'portaria_data', 'boletim_numero', 'boletim_data')
        }),
        ('Encerramento / Dispensa', {
            'fields': ('data_desligamento', 'motivo_desligamento', 'doc_desligamento', 'observacao'),
            'classes': ('collapse',), # Deixa esta área recolhida (clique para expandir)
        }),
    )

    def is_ativo_display(self, obj):
        return obj.is_ativo
    is_ativo_display.boolean = True
    is_ativo_display.short_description = "Ativo?"

@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'pag', 'empresa', 'vigencia_fim')
    search_fields = ('numero', 'pag', 'empresa__razao_social')
    autocomplete_fields = ['empresa']

from .models import PrestacaoContas, Setor, CargoRegimental, PrestacaoContasSetor, ApontamentoCorrecaoSetor

@admin.register(PrestacaoContas)
class PrestacaoContasAdmin(admin.ModelAdmin):
    list_display = ('contrato', 'mes_referencia', 'ano_referencia', 'data_envio', 'agente')
    list_filter = ('ano_referencia', 'mes_referencia')
    search_fields = ('contrato__numero', 'agente__nome_de_guerra')
    readonly_fields = ('data_envio',)

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sigla', 'ordem')
    search_fields = ('nome', 'sigla')
    ordering = ('ordem', 'nome')

@admin.register(CargoRegimental)
class CargoRegimentalAdmin(admin.ModelAdmin):
    list_display = ('cargo', 'setor', 'agente', 'ativo')
    list_filter = ('setor', 'ativo')
    search_fields = ('cargo', 'agente__nome_de_guerra')
    autocomplete_fields = ['setor', 'agente']

@admin.register(PrestacaoContasSetor)
class PrestacaoContasSetorAdmin(admin.ModelAdmin):
    list_display = ('setor', 'mes_referencia', 'ano_referencia', 'data_envio', 'agente')
    list_filter = ('ano_referencia', 'mes_referencia', 'status')
    search_fields = ('setor__nome', 'setor__sigla', 'agente__nome_de_guerra')
    readonly_fields = ('data_envio',)

@admin.register(ApontamentoCorrecaoSetor)
class ApontamentoCorrecaoSetorAdmin(admin.ModelAdmin):
    list_display = ('prestacao', 'autor', 'data_registro')
    search_fields = ('prestacao__setor__nome', 'autor__username')