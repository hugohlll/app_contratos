from django.urls import path
from contratos.views import public, militar, auditoria, auth

urlpatterns = [
    # --- ÁREA PÚBLICA (Módulo public.py) ---
    path('', public.pesquisa_publica, name='pesquisa'),
    path('contrato/<int:contrato_id>/', public.detalhe_contrato, name='detalhe_contrato'),
    path('transparencia/', public.relatorio_transparencia, name='transparencia'),
    path('transparencia/exportar/', public.exportar_transparencia_csv, name='exportar_transparencia_csv'),

    # --- ÁREA DO MILITAR (Módulo militar.py) ---
    path('militar/', militar.consulta_militar, name='consulta_militar'),
    path('militar/exportar/', militar.exportar_historico_militar_csv, name='exportar_historico_militar_csv'),

    # --- ÁREA RESTRITA / AUDITORIA (Módulo auditoria.py) ---
    path('auditoria/', auditoria.painel_controle, name='painel_controle'),

    # Exportações do Painel
    path('auditoria/exportar/', auditoria.exportar_csv, name='exportar_csv'),
    path('auditoria/vencimentos/csv/', auditoria.exportar_vencimentos_csv, name='exportar_vencimentos_csv'),
    path('auditoria/qualificacao/csv/', auditoria.exportar_qualificacao_csv, name='exportar_qualificacao_csv'),

    # Relatório por Período
    path('auditoria/relatorio/periodo/', auditoria.relatorio_por_periodo, name='relatorio_periodo'),
    path('auditoria/relatorio/periodo/csv/', auditoria.exportar_relatorio_periodo_csv, name='exportar_periodo_csv'),

    # --- AUTENTICAÇÃO (Módulo auth.py) ---
    path('sair/', auth.sair, name='sair_do_sistema'),
]