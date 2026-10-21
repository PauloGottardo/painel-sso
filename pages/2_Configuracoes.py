import streamlit as st

import banco

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")
banco.logo_lateral()

st.title("⚙️ Configurações")
st.caption("Cadastre as opções que aparecem nas listas da tela de Cadastro de Desvios.")

# mensagem que sobrevive ao recarregamento da página
if "aviso" in st.session_state:
    tipo_aviso, texto = st.session_state.pop("aviso")
    if tipo_aviso == "ok":
        st.success(texto)
    else:
        st.error(texto)

LISTAS = {
    "obra": ("Obras", "Nome da obra"),
    "local": ("Locais", "Nome do local"),
    "tipo": ("Tipos de desvio", "Nome do tipo de desvio"),
    "categoria": ("Categorias", "Nome da categoria"),
    "empreiteira": ("Empreiteiras", "Nome da empreiteira"),
}
ERROS = {
    "vazio": "Digite um nome antes de adicionar.",
    "longo": "O nome é muito longo (máximo de 60 caracteres).",
    "duplicado": "Esse item já está cadastrado.",
}

lista = st.radio(
    "Escolha a lista",
    list(LISTAS),
    format_func=lambda k: LISTAS[k][0],
    horizontal=True,
)
nome, rotulo = LISTAS[lista]
atuais = banco.opcoes(lista)

st.subheader(nome)
if atuais:
    st.dataframe({nome: atuais}, hide_index=True, use_container_width=True)
else:
    st.warning("Nenhum item cadastrado nesta lista. Adicione pelo menos um.")

st.markdown("##### Adicionar")
with st.form(f"add_{lista}", clear_on_submit=True):
    novo = st.text_input(rotulo)
    if st.form_submit_button("Adicionar", type="primary"):
        resultado = banco.adicionar_opcao(lista, novo)
        if resultado == "ok":
            st.session_state["aviso"] = ("ok", f"Item adicionado em {nome}.")
        else:
            st.session_state["aviso"] = ("erro", ERROS[resultado])
        st.rerun()

if atuais:
    st.markdown("##### Remover")
    with st.form(f"rem_{lista}", clear_on_submit=True):
        remover = st.multiselect("Selecione os itens para remover", atuais)
        if st.form_submit_button("Remover selecionados"):
            if remover:
                banco.remover_opcoes(lista, remover)
                st.session_state["aviso"] = ("ok", f"{len(remover)} item(ns) removido(s).")
            else:
                st.session_state["aviso"] = ("erro", "Selecione ao menos um item.")
            st.rerun()
    st.caption(
        "Remover um item não apaga os desvios já registrados com ele. "
        "Ele só deixa de aparecer nas listas do cadastro."
    )