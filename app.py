import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import numpy as np
from ofxparse import OfxParser
from unidecode import unidecode

st.set_page_config(page_title="Comparador NIBO", layout="wide")
st.title("📊 Comparador de Lançamentos - PDF/OFX vs Excel")

st.markdown("""
Envie um **extrato bancário (PDF ou OFX)** e um **Excel com lançamentos** para comparar:

- Lançamentos faltando no Excel
- Lançamentos faltando no Extrato
- Lançamentos com valor divergente
""")

# Uploads
excel_file = st.file_uploader("📁 Envie o Excel de lançamentos (.xlsx)", type="xlsx")
extrato_file = st.file_uploader("📄 Envie o extrato bancário (PDF ou OFX)", type=["pdf", "ofx"])

def normalizar_descricao(texto):
    return re.sub(r'\s+', ' ', unidecode(str(texto)).strip().lower())

if st.button("🔍 Comparar") and excel_file and extrato_file:

    # 📥 Carregar Excel com estrutura fixa
    df_excel = pd.read_excel(excel_file)

    if not all(c in df_excel.columns for c in ["Data", "Descricao", "Valor (R$)"]):
        st.error("❌ A planilha deve conter as colunas: 'Data', 'Descricao' e 'Valor (R$)'")
        st.stop()

    df_excel = df_excel.rename(columns={
        "Data": "Data",
        "Descricao": "Descrição",
        "Valor (R$)": "Valor"
    })
    df_excel["Data"] = pd.to_datetime(df_excel["Data"]).dt.strftime("%Y-%m-%d")
    df_excel["Descrição"] = df_excel["Descrição"].fillna("").astype(str).apply(normalizar_descricao)
    df_excel["Valor"] = pd.to_numeric(df_excel["Valor"], errors="coerce").round(2)

    # 📥 Carregar PDF ou OFX
    dados = []

    if extrato_file.name.endswith(".pdf"):
        with pdfplumber.open(extrato_file) as pdf:
            for p in pdf.pages:
                text = p.extract_text()
                for linha in text.split("\n"):
                    linha = linha.strip()
                    match = re.match(r"(\d{2}/\d{2})\s+(.+?)\s+([\d\.,]+)([DC])$", linha)
                    if match:
                        data_parcial = match.group(1)
                        desc = match.group(2).strip()
                        valor_str = match.group(3).replace(".", "").replace(",", ".")
                        tipo = match.group(4)

                        ano = "2025"  # fixo, pode ser ajustado dinamicamente se quiser
                        data_formatada = pd.to_datetime(f"{data_parcial}/{ano}", dayfirst=True).strftime("%Y-%m-%d")

                        valor = float(valor_str)
                        if tipo == "D":
                            valor *= -1

                        dados.append({
                            "Data": data_formatada,
                            "Descrição": normalizar_descricao(desc),
                            "Valor": round(valor, 2)
                        })

    elif extrato_file.name.endswith(".ofx"):
        content = extrato_file.read()
        try:
            decoded = content.decode('utf-8')
        except UnicodeDecodeError:
            decoded = content.decode('latin-1')
        ofx = OfxParser.parse(io.StringIO(decoded))
        for t in ofx.account.statement.transactions:
            dados.append({
                "Data": t.date.strftime("%Y-%m-%d"),
                "Descrição": normalizar_descricao(t.memo),
                "Valor": round(t.amount, 2)
            })

    if not dados:
        st.warning("❌ Nenhum lançamento encontrado no extrato.")
        st.stop()

    df_extrato = pd.DataFrame(dados)
    df_extrato["Valor"] = pd.to_numeric(df_extrato["Valor"], errors="coerce").round(2)

    # 🔍 Comparação por chave
    df_extrato["Chave"] = df_extrato["Data"] + "|" + df_extrato["Descrição"] + "|" + df_extrato["Valor"].astype(str)
    df_excel["Chave"] = df_excel["Data"] + "|" + df_excel["Descrição"] + "|" + df_excel["Valor"].astype(str)

    faltando_no_excel = df_extrato[~df_extrato["Chave"].isin(df_excel["Chave"])].drop(columns=["Chave"])
    faltando_no_extrato = df_excel[~df_excel["Chave"].isin(df_extrato["Chave"])].drop(columns=["Chave"])

    # ⚠️ Comparar lançamentos com mesma data + descrição e valores diferentes (com tolerância)
    df_merged = pd.merge(
        df_excel, df_extrato,
        on=["Data", "Descrição"],
        how="inner",
        suffixes=("_excel", "_extrato")
    )

    df_merged = df_merged[
        df_merged["Valor_excel"].notnull() &
        df_merged["Valor_extrato"].notnull()
    ]
    df_merged["Valor_excel"] = pd.to_numeric(df_merged["Valor_excel"], errors="coerce")
    df_merged["Valor_extrato"] = pd.to_numeric(df_merged["Valor_extrato"], errors="coerce")

    mascara_diferente = ~np.isclose(
        df_merged["Valor_excel"].values,
        df_merged["Valor_extrato"].values,
        atol=0.01
    )

    divergentes = df_merged.loc[mascara_diferente, ["Data", "Descrição", "Valor_excel", "Valor_extrato"]]

    # 📋 Exibir resultados
    st.subheader("❌ Lançamentos faltando no Excel")
    st.dataframe(faltando_no_excel, use_container_width=True)

    st.subheader("❌ Lançamentos faltando no Extrato")
    st.dataframe(faltando_no_extrato, use_container_width=True)

    st.subheader("⚠️ Lançamentos com valor divergente")
    st.dataframe(divergentes, use_container_width=True)

