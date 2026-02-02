import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(
    page_title="Painel de Auditoria",
    page_icon="📊",
    layout="wide"
)

# Estilização CSS customizada para cards
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: transparent !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
    }
</style>
""", unsafe_allow_html=True)

# Título Principal
st.title("📊 Painel de Controle de Auditoria")

# --- MOCK DATA GENERATION (Simulando o que viria do Django) ---
# 1. Monitoramento de Vencimentos
vencimentos_data = {
    'Militar': ['Sgt Silva', 'Ten Oliveira', 'Cap Souza', 'Maj Lima', 'Sgt Costa'],
    'Dias Restantes': [2, 5, 12, 14, 30],
    'Função': ['Fiscal Setorial', 'Fiscal Técnico', 'Gestor', 'Fiscal Admin', 'Fiscal Setorial'],
    'Contrato': ['001/2024', '002/2024', '003/2024', '004/2024', '005/2024']
}
df_vencimentos = pd.DataFrame(vencimentos_data)
# Classificação
def classify_vencimento(dias):
    if dias <= 7: return 'Crítico'
    elif dias <= 15: return 'Alerta'
    else: return 'Normal'
df_vencimentos['Status'] = df_vencimentos['Dias Restantes'].apply(classify_vencimento)

# 2. Radar de Permanência
permanencia_data = {
    'Militar': ['Sgt A', 'Sgt B', 'Sgt C', 'Ten D', 'Cap E'],
    'Dias Totais': [800, 750, 400, 380, 100],
    'Tempo Formatado': ['2a 2m', '2a 0m', '1a 1m', '1a 0m', '3m']
}
df_permanencia = pd.DataFrame(permanencia_data)

# 3. Qualificação
qualificacao_stats = {'Em Dia': 45, 'Vencidos': 5, 'Sem Curso': 2}

# 4. Sobrecarga
sobrecarga_data = {
    'Militar': ['Sgt X', 'Sgt Y', 'Ten Z', 'Cap W', 'Sgt K'],
    'Atuações': [8, 6, 5, 4, 4]
}
df_sobrecarga = pd.DataFrame(sobrecarga_data)

# 5. Contratos em Risco (Sem Fiscal Ativo)
contratos_risco_data = {
    'Contrato': ['010/2023 - Limpeza', '015/2023 - Segurança'],
    'Motivo': ['Sem Fiscal Técnico', 'Sem Fiscal Administrativo']
}
df_risco = pd.DataFrame(contratos_risco_data)


# --- LAYOUT DO DASHBOARD ---

# Sidebar
st.sidebar.header("Filtros Globais")
st.sidebar.markdown("---")
st.sidebar.info("Este painel demonstra a nova interface interativa usando Streamlit.")

# SEÇÃO 1: VISÃO GERAL E ALERTAS
st.subheader("1. Monitoramento de Vencimentos (Designações)")
col1, col2, col3, col4 = st.columns(4)

critico = df_vencimentos[df_vencimentos['Status'] == 'Crítico'].shape[0]
alerta = df_vencimentos[df_vencimentos['Status'] == 'Alerta'].shape[0]
normal = df_vencimentos[df_vencimentos['Status'] == 'Normal'].shape[0]

with col1:
    st.metric("Crítico (≤ 7 dias)", f"{critico}", delta_color="inverse")
with col2:
    st.metric("Alerta (8-15 dias)", f"{alerta}", delta_color="inverse")
with col3:
    st.metric("Normal (> 15 dias)", f"{normal}")
with col4:
    st.metric("Total Monitorado", f"{len(df_vencimentos)}")

# Tabela Top 5 Vencimentos
with st.expander("Ver Próximos Vencimentos", expanded=True):
    st.dataframe(
        df_vencimentos.sort_values('Dias Restantes').style.apply(
            lambda x: ['background-color: #ffcccb' if v <= 7 else 'background-color: #fff3cd' if v <= 15 else '' for v in x], 
            subset=['Dias Restantes']
        ),
        use_container_width=True
    )

st.divider()

# SEÇÃO 2: RADAR DE PERMANÊNCIA E QUALIFICAÇÃO
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("2. Radar de Permanência (> 2 anos)")
    st.caption("Agentes com maior tempo de atuação contínua no mesmo contrato/função.")
    
    # Gráfico de barras horizontal para permanência
    st.bar_chart(
        df_permanencia.set_index('Militar')['Dias Totais'],
        color="#ff4b4b",
        horizontal=True
    )
    
with c2:
    st.subheader("3. Qualificação da Equipe")
    df_qual = pd.DataFrame.from_dict(qualificacao_stats, orient='index', columns=['Quantidade'])
    st.dataframe(df_qual, use_container_width=True)
    
    # Donut chart simples usando altair ou plotly poderia ser melhor, mas usando st.bar_chart por simplicidade
    st.bar_chart(df_qual)

st.divider()

# SEÇÃO 3: SOBRECARGA E RISCOS
c3, c4 = st.columns(2)

with c3:
    st.subheader("4. Sobrecarga de Trabalho")
    st.caption("Agentes com maior número de designações simultâneas.")
    st.bar_chart(df_sobrecarga.set_index('Militar')['Atuações'])

with c4:
    st.subheader("5. Contratos em Risco (Atenção!)")
    st.error(f"Existem {len(df_risco)} contratos com pendências críticas de fiscalização.")
    st.dataframe(df_risco, use_container_width=True)

st.markdown("---")
st.caption("Protótipo de Painel de Auditoria - Versão Streamlit v0.2")
