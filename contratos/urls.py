from django.urls import path
from django.contrib.auth import views as auth_views
from contratos.views import public, militar, auditoria, auth, portal, users

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
    path('auditoria/exportar.csv', auditoria.exportar_csv, name='exportar_csv'),
    path('auditoria/vencimentos.csv', auditoria.exportar_vencimentos_csv, name='exportar_vencimentos_csv'),
    path('auditoria/qualificacao.csv', auditoria.exportar_qualificacao_csv, name='exportar_qualificacao_csv'),

    # Relatório por Período
    path('auditoria/relatorio/periodo/', auditoria.relatorio_por_periodo, name='relatorio_periodo'),
    path('auditoria/relatorio/periodo.csv', auditoria.exportar_relatorio_periodo_csv, name='exportar_periodo_csv'),

    # --- AUTENTICAÇÃO (Módulo auth.py + LoginView) ---
    path('login/', auth_views.LoginView.as_view(template_name='contratos/login.html'), name='login'),
    path('sair/', auth.sair, name='sair_do_sistema'),
    
    # --- PORTAL DO LANÇADOR (SIMPLIFICADO) ---
    path('portal/', portal.portal_home, name='portal_home'),
    
    # Empresas
    # Empresas
    path('portal/empresas/', portal.listar_empresas, name='listar_empresas'),
    path('portal/empresas/exportar.csv', portal.exportar_empresas_csv, name='exportar_empresas_csv'),
    path('portal/empresas/nova/', portal.nova_empresa, name='nova_empresa'),
    path('portal/empresas/editar/<int:pk>/', portal.editar_empresa, name='editar_empresa'),
    
    # Contratos
    path('portal/contratos/', portal.listar_contratos, name='listar_contratos'),
    path('portal/contratos/<int:pk>/', portal.detalhe_contrato, name='detalhe_contrato_portal'),
    path('portal/contratos/exportar.csv', portal.exportar_contratos_csv, name='exportar_contratos_csv'),
    path('portal/contratos/novo/', portal.novo_contrato, name='novo_contrato'),
    path('portal/contratos/editar/<int:pk>/', portal.editar_contrato, name='editar_contrato'),
    
    # Agentes
    path('portal/agentes/', portal.listar_agentes, name='listar_agentes'),
    path('portal/agentes/exportar.csv', portal.exportar_agentes_csv, name='exportar_agentes_csv'),
    path('portal/agentes/novo/', portal.novo_agente, name='novo_agente'),
    path('portal/agentes/editar/<int:pk>/', portal.editar_agente, name='editar_agente'),
    
    # Comissões
    path('portal/comissoes/', portal.listar_comissoes, name='listar_comissoes'),
    path('portal/comissoes/exportar.csv', portal.exportar_comissoes_csv, name='exportar_comissoes_csv'),
    path('portal/comissoes/nova/', portal.nova_comissao, name='nova_comissao'),
    path('portal/comissoes/editar/<int:pk>/', portal.editar_comissao, name='editar_comissao'),
    
    # Designações (Vinculadas a Comissão)
    path('portal/comissoes/<int:comissao_id>/designacao/nova/', portal.nova_designacao_comissao, name='nova_designacao_comissao'),
    path('portal/designacoes/editar/<int:pk>/', portal.editar_designacao_comissao, name='editar_designacao_comissao'),

    # --- GERENCIAMENTO DE USUÁRIOS (Módulo users.py) ---
    path('portal/usuarios/', users.listar_usuarios, name='listar_usuarios'),
    path('portal/usuarios/novo/', users.novo_usuario, name='novo_usuario'),
    path('portal/usuarios/editar/<int:pk>/', users.editar_usuario, name='editar_usuario'),
    path('portal/usuarios/excluir/<int:pk>/', users.excluir_usuario, name='excluir_usuario'),
    path('portal/alterar-senha/', users.alterar_senha, name='alterar_senha'),
]