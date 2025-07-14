import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
from ofxparse import OfxParser

st.set_page_config(page_title="Comparador NIBO", layout="wide")
st.title("📊 Comparador de Lançamentos - PDF/OFX vs Excel")

st.markdown("""
Faça upload de um **extrato bancário (PDF ou OFX)** e um **Excel com lançamentos** para comparar:

- Lançamentos faltantes no Excel
- Lançamentos faltantes no extrato
- Lançamentos com valor divergente
""")

# Uploads
excel_file = st.file_uploader("📁 Envie o Excel de lançamentos (.xlsx)", type="xlsx")
extrato_file = st.file_uploader("📄 Envie o extrato bancário (PDF ou OFX)", type=["pdf", "ofx"])

if st.button("🔍 Comparar") and excel_file and extrato_file:
    # 📥 Carregar Excel
    df_excel = pd.read_excel(excel_file)
    df_excel.columns = [c.strip().lower() for c in df_excel.columns]

    col_data = next((c for c in df_excel.columns if 'data' in c), None)
    col_valor = next((c for c in df_excel.columns if 'valor' in c), None)
    col_desc = next((c for c in df_excel.columns if 'hist' in c or 'descri' in c), None)

    if not (col_data and col_valor and col_desc):
        st.error("❌ Não foi possível identificar colunas 'Data', 'Descrição' e 'Valor' no Excel.")
        st.stop()

    df_excel = df_excel.rename(columns={
        col_data: "Data",
        col_valor: "Valor",
        col_desc: "Descrição"
    })
    df_excel["Data"] = pd.to_datetime(df_excel["Data"]).dt.strftime("%Y-%m-%d")
    df_excel["Descrição"] = df_excel["Descrição"].astype(str).str.strip()
    df_excel["Valor"] = df_excel["Valor"].astype(float).round(2)

    # 📥 Carregar PDF ou OFX
    dados = []

    if extrato_file.name.endswith(".pdf"):
        with pdfplumber.open(extrato_file) as pdf:
            for p in pdf.pages:
                text = p.extract_text()
                for linha in text.split("\n"):
                    match = re.match(r"(\d{2}[\/\-]\d{2}[\/\-]\d{4})\s+(.+?)\s+R\$ *([\d\.,\-]+)", linha)
                    if match:
                        data = pd.to_datetime(match.group(1), dayfirst=True).strftime("%Y-%m-%d")
                        desc = match.group(2).strip()
                        val = float(match.group(3).replace(".", "").replace(",", "."))
                        dados.append({"Data": data, "Descrição": desc, "Valor": val})
    elif extrato_file.name.endswith(".ofx"):
        ofx = OfxParser.parse(io.StringIO(extrato_file.read().decode()))
        for t in ofx.account.statement.transactions:
            dados.append({
                "Data": t.date.strftime("%Y-%m-%d"),
                "Descrição": t.memo.strip(),
                "Valor": round(t.amount, 2)
            })

    if not dados:
        st.warning("Nenhum lançamento encontrado no extrato.")
        st.stop()

    df_extrato = pd.DataFrame(dados)

    # 🔍 Comparação
    df_extrato["Chave"] = df_extrato["Data"] + "|" + df_extrato["Descrição"] + "|" + df_extrato["Valor"].astype(str)
    df_excel["Chave"] = df_excel["Data"] + "|" + df_excel["Descrição"] + "|" + df_excel["Valor"].astype(str)

    faltando_no_excel = df_extrato[~df_extrato["Chave"].isin(df_excel["Chave"])].drop(columns=["Chave"])
    faltando_no_extrato = df_excel[~df_excel["Chave"].isin(df_extrato["Chave"])].drop(columns=["Chave"])

    df_merged = pd.merge(
        df_excel, df_extrato,
        on=["Data", "Descrição"],
        how="inner",
        suffixes=("_excel", "_extrato")
    )
    divergentes = df_merged[df_merged["Valor_excel"] != df_merged["Valor_extrato"]][["Data", "Descrição", "Valor_excel", "Valor_extrato"]]

    # 📋 Exibir resultados
    st.subheader("❌ Lançamentos faltando no Excel")
    st.dataframe(faltando_no_excel, use_container_width=True)

    st.subheader("❌ Lançamentos faltando no Extrato")
    st.dataframe(faltando_no_extrato, use_container_width=True)

    st.subheader("⚠️ Lançamentos com valor divergente")
    st.dataframe(divergentes, use_container_width=True)
