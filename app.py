import streamlit as st
import pandas as pd
import os
from datetime import datetime, date

# 1. MAPEAMENTO HIERÁRQUICO REGULAMENTAR (Cel à Sd)
ORDEM_HIERARQUICA = {
    "Cel": 1, "Ten Cel": 2, "Maj": 3, "Cap": 4, 
    "1º Ten": 5, "2º Ten": 6, "Subten": 7,
    "1º Sgt": 8, "2º Sgt": 9, "3º Sgt": 10, "Cb": 11, "Sd": 12
}

HOJE = date(2026, 10, 6)
ARQUIVO_HISTORICO = "historico_procedimentos.csv"

# DEFINIÇÃO DE IDENTIDADE DO APP
st.set_page_config(page_title="Controle de Encarregados", layout="wide")
st.title("🛡️ Controle de Encarregados")
st.caption(f"Polícia Militar de Roraima — Data Atual do Sistema: {HOJE.strftime('%d/%m/%Y')}")

# =================================================================================================
# GESTÃO DO BANCO DE DADOS PERSISTENTE (SALVAMENTO AUTOMÁTICO)
# =================================================================================================
if "procedimentos" not in st.session_state:
    if os.path.exists(ARQUIVO_HISTORICO):
        st.session_state.procedimentos = pd.read_csv(ARQUIVO_HISTORICO).to_dict(orient="records")
    else:
        st.session_state.procedimentos = []

def salvar_dados_automaticamente():
    df_salvar = pd.DataFrame(st.session_state.procedimentos)
    df_salvar.to_csv(ARQUIVO_HISTORICO, index=False)

# =================================================================================================
# ENTRADA DA PLANILHA CORRIGIDA (.xlsx)
# =================================================================================================
st.markdown("### 📊 Banco de Dados do Efetivo")
arquivo_publicado = st.file_uploader(
    "Faça o upload da planilha 'planilha_encarregados_corrigida.xlsx' baixada:", 
    type=["xlsx", "csv"]
)

if arquivo_publicado is None:
    st.info("💡 Por favor, faça o upload da planilha corrigida para carregar as relações de Coronel a Soldado.")
    st.stop()
else:
    try:
        if arquivo_publicado.name.endswith(".xlsx"):
            df_input = pd.read_excel(arquivo_publicado)
        else:
            df_input = pd.read_csv(arquivo_publicado)
            
        df_input = df_input.rename(columns={col: col.strip() for col in df_input.columns})
        
        # Injeta colunas de controle do app na memória
        if "Habilitado" not in df_input.columns:
            df_input["Habilitado"] = True
        if "Data_Livre" not in df_input.columns:
            df_input["Data_Livre"] = date(2026, 9, 1)
            
        # Sincroniza as datas livres dos militares com os processos salvos no arquivo de persistência
        for p in st.session_state.procedimentos:
            if p["Status"] == "Em Andamento":
                df_input.loc[df_input["Nome"] == p["Encarregado_Nome"], "Data_Livre"] = None
            elif p["Status"] == "Concluído" and pd.notna(p.get("Data_Entrega")):
                df_input.loc[df_input["Nome"] == p["Encarregado_Nome"], "Data_Livre"] = p["Data_Entrega"]

        if "militares_db" not in st.session_state or st.sidebar.button("🔄 Sincronizar Efetivo"):
            st.session_state.militares_db = df_input
            st.success(f"Planilha integrada! {len(df_input)} militares carregados por antiguidade hierárquica.")
    except Exception as e:
        st.error(f"Erro de processamento: {e}")
        st.stop()

# --- MOTOR DE ORDENAÇÃO POR ESCALA HIERÁRQUICA ---
nomes_ocupados = [p["Encarregado_Nome"] for p in st.session_state.procedimentos if p["Status"] == "Em Andamento"]

df_mestre = st.session_state.militares_db.copy()
df_mestre["Dias_Livres_Num"] = df_mestre["Data_Livre"].apply(lambda x: (HOJE - pd.to_datetime(x).date()).days if pd.notna(x) else 0)
df_mestre["Peso_Hierarquico"] = df_mestre["Posto/Grad"].map(ORDEM_HIERARQUICA).fillna(99)

# Ordena por Antiguidade (Cel a Sd). Mesmos postos desempatam por quem está livre há mais tempo.
df_mestre = df_mestre.sort_values(by=["Peso_Hierarquico", "Dias_Livres_Num"], ascending=[True, False])

def texto_dias(row):
    if row["Nome"] in nomes_ocupados: return "Em procedimento ativo"
    return f"Livre há {row['Dias_Livres_Num']} dias"
df_mestre["Situação / Dias Livres"] = df_mestre.apply(texto_dias, axis=1)

# --- NAVEGAÇÃO DO APP ---
aba1, aba2, aba3 = st.tabs(["📝 Instaurar Procedimento (Trava Hierárquica)", "✅ Registrar Entrega de Solução", "🔍 Relações Nominais e Filtros"])

# ---- ABA 1: INSTAURAÇÃO DE PORTARIA ----
with aba1:
    st.subheader("Nova Portaria de Investigação")
    col_p1, col_p2, col_p3 = st.columns(3)
    num_portaria = col_p1.text_input("Portaria Nº", placeholder="Ex: 015/2026")
    tipo_procedimento = col_p2.selectbox("Tipo de Feito", ["IPM", "Sindicância", "FATD"])
    posto_investigado = col_p3.selectbox("Posto/Graduação do Investigado:", list(ORDEM_HIERARQUICA.keys()))
    
    peso_limite_investigado = ORDEM_HIERARQUICA[posto_investigado]

    # Trava Legal Militar: Encarregado deve ser Habilitado, Livre e MAIS ANTIGO que o investigado
    df_aptos_escala = df_mestre[
        (df_mestre["Habilitado"] == True) & 
        (~df_mestre["Nome"].isin(nomes_ocupados)) & 
        (df_mestre["Peso_Hierarquico"] <= peso_limite_investigado)
    ]
    
    if df_aptos_escala.empty:
        st.error(f"❌ Erro de Escala: Não existem Militares Livres com precedência hierárquica para investigar um {posto_investigado}!")
    else:
        with st.form("form_instaurar"):
            opcoes_select = df_aptos_escala["Posto/Grad"] + " [" + df_aptos_escala["Quadro"] + "] - " + df_aptos_escala["Nome"] + " (" + df_aptos_escala["Situação / Dias Livres"] + ")"
            militar_designado = st.selectbox("Selecione o Encarregado da Lista Filtrada:", opcoes_select)
            
            if st.form_submit_button("Confirmar Designação"):
                idx_sel = opcoes_select[opcoes_select == militar_designado].index
                dados_escolhidos = df_aptos_escala.loc[idx_sel]
                
                nome_militar = dados_escolhidos["Nome"].values[0]
                posto_militar = dados_escolhidos["Posto/Grad"].values[0]
                
                st.session_state.procedimentos.append({
                    "Portaria": num_portaria, "Tipo": tipo_procedimento,
                    "Encarregado_Nome": nome_militar, "Posto": posto_militar,
                    "Investigado_Posto": posto_investigado, "Status": "Em Andamento", "Data_Entrega": None
                })
                st.session_state.militares_db.loc[st.session_state.militares_db["Nome"] == nome_militar, "Data_Livre"] = None
                salvar_dados_automaticamente()
                st.success(f"Portaria {num_portaria} registrada e gravada automaticamente!")
                st.rerun()

# ---- ABA 2: REGISTRAR ENTREGA DE FEITOS ----
with aba2:
    st.subheader("Fechamento de Feitos")
    ativos = [p for p in st.session_state.procedimentos if p["Status"] == "Em Andamento"]
    
    if not ativos:
        st.info("Nenhum procedimento pendente de entrega.")
    else:
        opcoes_entrega = [f"{p['Portaria']} | {p['Posto']} {p['Encarregado_Nome']}" for p in ativos]
        procedimento_escolhido = st.selectbox("Selecione o feito a ser encerrado:", opcoes_entrega)
        data_de_entrega = st.date_input("Data de entrega da solução:", HOJE)
        
        if st.button("Homologar Entrega e Liberar Militar"):
            p_alvo = procedimento_escolhido.split(" | ")[0]
            for p in st.session_state.procedimentos:
                if p["Portaria"] == p_alvo:
                    p["Status"] = "Concluído"
                    p["Data_Entrega"] = str(data_de_entrega)
                    st.session_state.militares_db.loc[st.session_state.militares_db["Nome"] == p["Encarregado_Nome"], "Data_Livre"] = data_de_entrega
            salvar_dados_automaticamente()
            st.success("Militar liberado! Os dados foram salvos no arquivo de persistência.")
            st.rerun()

# ---- ABA 3: RELAÇÕES NOMINAIS ENXUTAS ----
with aba3:
    st.subheader("🔍 Filtros de Consulta")
    c_f1, c_f2, c_f3 = st.columns(3)
    f_nome = c_f1.text_input("Filtrar por Nome:", placeholder="Digite para buscar...")
    f_posto = c_f2.multiselect("Filtrar por Posto/Graduação:", options=list(ORDEM_HIERARQUICA.keys()))
    f_dias = c_f3.number_input("Mínimo de Dias Livres:", min_value=0, value=0)
    
    df_filtrado_geral = df_mestre.copy()
    if f_nome:
        df_filtrado_geral = df_filtrado_geral[df_filtrado_geral["Nome"].str.contains(f_nome, case=False)]
    if f_posto:
        df_filtrado_geral = df_filtrado_geral[df_filtrado_geral["Posto/Grad"].isin(f_posto)]
    if f_dias > 0:
        df_filtrado_geral = df_filtrado_geral[df_filtrado_geral["Dias_Livres_Num"] >= f_dias]
        
    st.markdown("---")
    st.subheader("📋 1ª Relação: Militares Habilitados (Ordem Decrescente de Antiguidade)")
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.write("🟢 **Livres para Escala**")
        df_l = df_filtrado_geral[(df_filtrado_geral["Habilitado"] == True) & (~df_filtrado_geral["Nome"].isin(nomes_ocupados))]
        st.dataframe(df_l[["Posto/Grad", "Quadro", "Nome", "Situação / Dias Livres"]], use_container_width=True, hide_index=True)
    with col_l2:
        st.write("🔴 **Com Procedimento Ativo**")
        df_o = df_filtrado_geral[(df_filtrado_geral["Habilitado"] == True) & (df_filtrado_geral["Nome"].isin(nomes_ocupados))]
        st.dataframe(df_o[["Posto/Grad", "Quadro", "Nome", "Situação / Dias Livres"]], use_container_width=True, hide_index=True)
        
    st.markdown("---")
    st.subheader("❌ 2ª Relação: Militares Não Habilitados")
    df_nh = df_filtrado_geral[df_filtrado_geral["Habilitado"] == False]
    st.dataframe(df_nh[["Posto/Grad", "Quadro", "Nome", "Situação / Dias Livres"]], use_container_width=True, hide_index=True)
