import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

st.set_page_config(page_title="Comparador NIBO", layout="wide")
st.title("📊 Comparador de Lançamentos - PDF vs Excel")

excel_file = st.file_uploader("📁 Envie o Excel (.xlsx)", type="xlsx")
pdf_file = st.file_uploader("📄 Envie o PDF do extrato", type="pdf")
if st.button("🔍 Comparar") and excel_file and pdf_file:
    # Carregar Excel
    df_excel = pd.read_excel(excel_file)
    df_excel.columns = [c.strip().lower() for c in df_excel.columns]
    col_data = next((c for c in df_excel.columns if 'data' in c), None)
    col_valor = next((c for c in df_excel.columns if 'valor' in c), None)
    col_desc = next((c for c in df_excel.columns if 'hist' in c or 'descri' in c), None)
    if not (col_data and col_valor and col_desc):
        st.error("❌ Colunas não encontradas no Excel.")
        st.stop()
    df_excel = df_excel.rename(columns={col_data: "Data", col_valor: "Valor", col_desc: "Descrição"})
    df_excel["Data"] = pd.to_datetime(df_excel["Data"]).dt.strftime("%Y-%m-%d")
    df_excel["Descrição"] = df_excel["Descrição"].astype(str).str.strip()
    df_excel["Valor"] = df_excel["Valor"].astype(float).round(2)

    # Extrair PDF
    dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for p in pdf.pages:
            text = p.extract_text()
            for linha in text.split("\n"):
                match = re.match(r"(\d{2}[\/\-]\d{2}[\/\-]\d{4})\s+(.+?)\s+R\$ *([\d\.,\-]+)", linha)
                if match:
                    data = pd.to_datetime(match.group(1), dayfirst=True).strftime("%Y-%m-%d")
                    desc = match.group(2).strip()
                    val = float(match.group(3).replace(".", "").replace(",", "."))
                    dados.append({"Data": data, "Descrição": desc, "Valor": val})
    df_pdf = pd.DataFrame(dados)

    # Comparar
    df_pdf["Chave"] = df_pdf["Data"] + "|" + df_pdf["Descrição"] + "|" + df_pdf["Valor"].astype(str)
    df_excel["Chave"] = df_excel["Data"] + "|" + df_excel["Descrição"] + "|" + df_excel["Valor"].astype(str)
    faltando_no_pdf = df_excel[~df_excel["Chave"].isin(df_pdf["Chave"])].drop(columns=["Chave"])
    faltando_no_excel = df_pdf[~df_pdf["Chave"].isin(df_excel["Chave"])].drop(columns=["Chave"])
    df_comb = pd.merge(df_excel, df_pdf, on=["Data","Descrição"], suffixes=("_exc","_pdf"))
    divergentes = df_comb[df_comb["Valor_exc"] != df_comb["Valor_pdf"]][["Data","Descrição","Valor_exc","Valor_pdf"]]

    # Exibir
    st.subheader("📋 Lançamentos não encontrados no PDF")
    st.dataframe(faltando_no_pdf)
    st.subheader("📋 Lançamentos não encontrados no Excel")
    st.dataframe(faltando_no_excel)
    st.subheader("⚠️ Valores divergentes")
    st.dataframe(divergentes)
