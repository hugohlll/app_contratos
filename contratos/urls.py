from django.urls import path
from .views import (
    portal, contratos, agentes, painel_controle, comissoes, api
)
from .views.auditoria import (
    exportar_csv, exportar_qualificacao_csv, exportar_vencimentos_csv,
    exportar_radar_permanencia_csv, exportar_sobrecarga_fiscais_csv,
    exportar_contratos_vencimento_csv, relatorio_por_periodo, exportar_relatorio_periodo_csv
)

urlpatterns = [
    path('', portal.home, name='portal_home'),
    path('ajuda/manual/', portal.manual_usuario, name='manual_usuario'),
    
    # ... Empresas ...
    path('empresas/', contratos.listar_empresas, name='listar_empresas'),
    path('empresas/nova/', contratos.criar_empresa, name='criar_empresa'),
    path('empresas/<int:id>/editar/', contratos.editar_empresa, name='editar_empresa'),
    path('empresas/<int:id>/excluir/', contratos.excluir_empresa, name='excluir_empresa'),

    # ... Contratos ...
    path('contratos/', contratos.listar_contratos, name='listar_contratos'),
    path('contratos/novo/', contratos.criar_contrato, name='criar_contrato'),
    path('contratos/<int:id>/', contratos.detalhe_contrato, name='detalhe_contrato'),
    path('contratos/<int:id>/editar/', contratos.editar_contrato, name='editar_contrato'),
    path('contratos/<int:id>/excluir/', contratos.excluir_contrato, name='excluir_contrato'),

    # ... Agentes (Militares) ...
    path('agentes/', agentes.listar_agentes, name='listar_agentes'),
    path('agentes/novo/', agentes.criar_agente, name='criar_agente'),
    path('agentes/<int:id>/', agentes.detalhe_agente, name='detalhe_agente'),
    path('agentes/<int:id>/editar/', agentes.editar_agente, name='editar_agente'),
    path('agentes/<int:id>/excluir/', agentes.excluir_agente, name='excluir_agente'),
    
    # ... Comissões ...
    path('comissoes/', comissoes.listar_comissoes, name='listar_comissoes'),
    path('contratos/<int:contrato_id>/comissoes/nova/', comissoes.criar_comissao, name='criar_comissao'),
    path('comissoes/<int:id>/', comissoes.detalhe_comissao, name='detalhe_comissao'),
    path('comissoes/<int:id>/editar/', comissoes.editar_comissao, name='editar_comissao'),
    path('comissoes/<int:id>/excluir/', comissoes.excluir_comissao, name='excluir_comissao'),
    
    # ... Membros de Comissão ...
    path('comissoes/<int:comissao_id>/membros/novo/', comissoes.adicionar_integrante, name='adicionar_integrante'),
    path('membros/<int:id>/editar/', comissoes.editar_integrante, name='editar_integrante'),
    path('membros/<int:id>/excluir/', comissoes.excluir_integrante, name='excluir_integrante'),
    path('membros/<int:id>/encerrar/', comissoes.encerrar_designacao, name='encerrar_designacao'),
    
    # ... Auditoria / Painel de Controle ...
    path('auditoria/', painel_controle.painel_controle, name='painel_controle'),
    path('auditoria/exportar/', exportar_csv, name='exportar_csv'),
    path('auditoria/exportar-qualificacao/', exportar_qualificacao_csv, name='exportar_qualificacao_csv'),
    path('auditoria/exportar-vencimentos/', exportar_vencimentos_csv, name='exportar_vencimentos_csv'),
    path('auditoria/exportar-radar/', exportar_radar_permanencia_csv, name='exportar_radar_permanencia_csv'),
    path('auditoria/exportar-sobrecarga/', exportar_sobrecarga_fiscais_csv, name='exportar_sobrecarga_fiscais_csv'),
    path('auditoria/exportar-contratos-risco/', exportar_contratos_vencimento_csv, name='exportar_contratos_vencimento_csv'),
    
    path('auditoria/relatorio-periodo/', relatorio_por_periodo, name='relatorio_periodo'),
    path('auditoria/relatorio-periodo/exportar/', exportar_relatorio_periodo_csv, name='exportar_relatorio_periodo_csv'),

    # ... Autocomplete API ...
    path('api/agentes/buscar/', api.buscar_agente_api, name='buscar_agente_api'),
]