import pandas as pd
import plotly.express as px
import streamlit as st

import banco

st.set_page_config(page_title="Painel SSO", page_icon="🦺", layout="wide")
banco.logo_lateral()

FORMATO_DATA = "DD/MM/YY"
CONFIG_DATAS = {
    "data": st.column_config.DateColumn("Data", format=FORMATO_DATA),
    "prazo": st.column_config.DateColumn("Prazo", format=FORMATO_DATA),
    "data_fechamento": st.column_config.DateColumn(
        "Data de fechamento", format=FORMATO_DATA
    ),
}

st.title("🦺 Painel de Desvios e Inspeções de SSO")

if banco.contar() == 0:
    st.info("Nenhum desvio cadastrado ainda. Use a página Cadastro no menu lateral.")
    st.stop()

dados = banco.listar()

# ---------- filtros ----------
st.sidebar.header("Filtros")
d_min, d_max = dados["data"].min().date(), dados["data"].max().date()
periodo = st.sidebar.date_input("Período", (d_min, d_max), min_value=d_min, max_value=d_max)

obras = st.sidebar.multiselect("Obra", sorted(dados["obra"].dropna().unique()))
empreiteiras = st.sidebar.multiselect("Empreiteira", sorted(dados["empreiteira"].dropna().unique()))
tipos = st.sidebar.multiselect("Tipo", sorted(dados["tipo"].dropna().unique()))
gravidades = st.sidebar.multiselect("Gravidade", sorted(dados["gravidade"].dropna().unique()))

df = dados.copy()
if isinstance(periodo, tuple) and len(periodo) == 2:
    ini, fim = pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1])
    df = df[(df["data"] >= ini) & (df["data"] <= fim)]
if obras:
    df = df[df["obra"].isin(obras)]
if empreiteiras:
    df = df[df["empreiteira"].isin(empreiteiras)]
if tipos:
    df = df[df["tipo"].isin(tipos)]
if gravidades:
    df = df[df["gravidade"].isin(gravidades)]

if df.empty:
    st.warning("Nenhum registro para os filtros selecionados.")
    st.stop()

# ---------- indicadores ----------
total = len(df)
abertos = int((~df["fechado"]).sum())
pct_fechados = 100 * df["fechado"].mean()
vencidos = int(df["vencido"].sum())
media_fechamento = df["dias_para_fechar"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Desvios registrados", total)
c2.metric("Em aberto", abertos)
c3.metric("% concluídos", f"{pct_fechados:.0f}%")
c4.metric("Vencidos (fora do prazo)", vencidos)
c5.metric(
    "Tempo médio p/ fechar",
    "—" if pd.isna(media_fechamento) else f"{media_fechamento:.1f} dias",
)

st.divider()

# ---------- gráficos ----------
esq, dir_ = st.columns(2)

with esq:
    semanal = (
        df.groupby([pd.Grouper(key="data", freq="W"), "tipo"])
        .size()
        .reset_index(name="quantidade")
    )
    fig = px.bar(
        semanal, x="data", y="quantidade", color="tipo",
        title="Evolução semanal de desvios", labels={"data": "Semana"},
    )
    st.plotly_chart(fig, use_container_width=True)

with dir_:
    por_cat = df["categoria"].value_counts().reset_index()
    por_cat.columns = ["categoria", "quantidade"]
    fig = px.bar(
        por_cat.sort_values("quantidade"), x="quantidade", y="categoria",
        orientation="h", title="Desvios por categoria",
    )
    st.plotly_chart(fig, use_container_width=True)

esq, dir_ = st.columns(2)

with esq:
    por_emp = (
        df.groupby(["empreiteira", "gravidade"]).size().reset_index(name="quantidade")
    )
    fig = px.bar(
        por_emp, x="empreiteira", y="quantidade", color="gravidade",
        title="Desvios por empreiteira e gravidade",
    )
    st.plotly_chart(fig, use_container_width=True)

with dir_:
    por_local = df["local"].value_counts().head(10).reset_index()
    por_local.columns = ["local", "quantidade"]
    fig = px.bar(
        por_local.sort_values("quantidade"), x="quantidade", y="local",
        orientation="h", title="Top 10 locais com mais ocorrências",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- pendências ----------
st.subheader("Pendências vencidas")
venc = df[df["vencido"]].sort_values("prazo")[
    ["id", "data", "obra", "local", "categoria", "empreiteira", "gravidade",
     "descricao", "responsavel", "prazo"]
]
if venc.empty:
    st.success("Nenhuma pendência vencida no filtro atual.")
else:
    st.dataframe(
        venc, use_container_width=True, hide_index=True,
        column_config=CONFIG_DATAS,
    )

with st.expander("Ver todos os registros filtrados"):
    st.dataframe(
        df, use_container_width=True, hide_index=True,
        column_config=CONFIG_DATAS,
    )