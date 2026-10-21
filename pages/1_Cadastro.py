from datetime import date, timedelta

import streamlit as st

import banco

st.set_page_config(page_title="Cadastro de Desvios", page_icon="📝", layout="wide")
banco.logo_lateral()

st.title("📝 Cadastro de Desvios")
st.caption("Preencha os campos e clique em Salvar. O registro aparece no painel na hora.")

obras = banco.opcoes("obra")
locais = banco.opcoes("local")
tipos = banco.opcoes("tipo")
categorias = banco.opcoes("categoria")
empreiteiras = banco.opcoes("empreiteira")

vazias = [
    nome for nome, itens in [
        ("Obras", obras), ("Locais", locais), ("Tipos de desvio", tipos),
        ("Categorias", categorias), ("Empreiteiras", empreiteiras),
    ] if not itens
]
if vazias:
    st.error(
        "Cadastre pelo menos um item na página Configurações para: "
        + ", ".join(vazias) + "."
    )
    st.stop()

with st.form("novo_desvio", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    data = c1.date_input("Data da inspeção", value=date.today(), format="DD/MM/YYYY")
    obra = c2.selectbox("Obra", obras)
    local = c3.selectbox("Local", locais)

    c4, c5, c6 = st.columns(3)
    tipo = c4.selectbox("Tipo", tipos)
    categoria = c5.selectbox("Categoria", categorias)
    gravidade = c6.selectbox("Gravidade", banco.GRAVIDADES)

    c7, c8, c9 = st.columns(3)
    empreiteira = c7.selectbox("Empreiteira", empreiteiras)
    responsavel = c8.text_input("Responsável pela correção")
    prazo = c9.date_input(
        "Prazo para correção",
        value=date.today() + timedelta(days=3),
        format="DD/MM/YYYY",
    )

    descricao = st.text_area("Descrição do desvio *", height=100)
    acao = st.text_area("Ação corretiva", height=100)

    salvar = st.form_submit_button("Salvar Ação", type="primary")

if salvar:
    if not descricao.strip():
        st.error("A descrição do desvio é obrigatória. Preencha os campos novamente.")
    elif prazo < data:
        st.error("O prazo não pode ser anterior à data da inspeção. Preencha novamente.")
    else:
        banco.inserir({
            "data": data,
            "obra": obra,
            "local": local,
            "tipo": tipo,
            "categoria": categoria,
            "empreiteira": empreiteira,
            "gravidade": gravidade,
            "descricao": descricao.strip(),
            "acao_corretiva": acao.strip(),
            "responsavel": responsavel.strip(),
            "prazo": prazo,
            "status": "Aberto",
        })
        st.success("Desvio salvo com sucesso!")

st.divider()
st.subheader("Últimos registros")
if banco.contar() == 0:
    st.info("Nenhum desvio cadastrado ainda.")
else:
    recentes = banco.listar().sort_values("id", ascending=False).head(5)
    st.dataframe(
        recentes[["id", "data", "obra", "local", "categoria", "gravidade", "status", "prazo"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "data": st.column_config.DateColumn("Data", format="DD/MM/YY"),
            "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YY"),
        },
    )