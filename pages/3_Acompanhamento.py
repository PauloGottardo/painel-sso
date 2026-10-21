from datetime import date

import pandas as pd
import streamlit as st

import banco

st.set_page_config(page_title="Acompanhamento", page_icon="✅", layout="wide")
banco.logo_lateral()

st.title("✅ Acompanhamento de Ações")
st.caption("Conclua, corrija ou exclua os desvios cadastrados.")

# mensagem que sobrevive ao recarregamento da página
if "aviso" in st.session_state:
    tipo_aviso, texto = st.session_state.pop("aviso")
    if tipo_aviso == "ok":
        st.success(texto)
    else:
        st.error(texto)

if banco.contar() == 0:
    st.info("Nenhum desvio cadastrado ainda.")
    st.stop()

STATUS = ["Aberto", "Concluído"]


def para_data(valor, padrao=None):
    if not valor:
        return padrao
    return pd.Timestamp(valor).date()


def com_atual(lista, atual):
    """Opções da lista; mantém o valor atual mesmo que tenha sido removido."""
    itens = banco.opcoes(lista)
    if atual and atual not in itens:
        itens = itens + [atual]
    return itens


def posicao(itens, valor):
    return itens.index(valor) if valor in itens else 0


# ---------- filtros ----------
df = banco.listar()

f1, f2 = st.columns(2)
situacao = f1.selectbox("Situação", ["Em aberto", "Vencidos", "Concluídos", "Todos"])
obra_f = f2.selectbox("Obra", ["Todas"] + sorted(df["obra"].dropna().unique()))

if situacao == "Em aberto":
    df = df[~df["fechado"]]
elif situacao == "Vencidos":
    df = df[df["vencido"]]
elif situacao == "Concluídos":
    df = df[df["fechado"]]
if obra_f != "Todas":
    df = df[df["obra"] == obra_f]

if df.empty:
    st.success("Nenhum desvio nesta situação.")
    st.stop()

if situacao in ("Em aberto", "Vencidos"):
    df = df.sort_values("prazo")
else:
    df = df.sort_values("id", ascending=False)

df["situacao"] = df["status"]
df.loc[df["vencido"], "situacao"] = "Vencido"

tabela = df[
    ["id", "data", "obra", "local", "categoria", "gravidade", "empreiteira",
     "responsavel", "prazo", "situacao"]
].reset_index(drop=True)

st.markdown(f"**{len(tabela)}** desvio(s). Clique em uma linha para abrir.")
evento = st.dataframe(
    tabela,
    hide_index=True,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "id": "Nº",
        "data": st.column_config.DateColumn("Data", format="DD/MM/YY"),
        "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YY"),
        "situacao": "Situação",
    },
)

linhas = evento.selection.rows
if not linhas:
    st.info("Selecione um desvio na tabela para concluir, editar ou excluir.")
    st.stop()

id_sel = int(tabela.iloc[linhas[0]]["id"])
reg = banco.obter(id_sel)
if not reg:
    st.error("Desvio não encontrado. Atualize a página.")
    st.stop()

st.divider()
st.subheader(f"Desvio nº {id_sel}")

# ---------- conclusão rápida ----------
if reg["status"] != "Concluído":
    if st.button("✅ Marcar como concluído hoje", type="primary", key=f"rapido_{id_sel}"):
        banco.atualizar(
            id_sel, {**reg, "status": "Concluído", "data_fechamento": date.today()}
        )
        st.session_state["aviso"] = ("ok", f"Desvio nº {id_sel} concluído.")
        st.rerun()

# ---------- edição completa ----------
obras = com_atual("obra", reg["obra"])
locais = com_atual("local", reg["local"])
tipos = com_atual("tipo", reg["tipo"])
categorias = com_atual("categoria", reg["categoria"])
empreiteiras = com_atual("empreiteira", reg["empreiteira"])
gravidades = banco.GRAVIDADES
k = id_sel  # sufixo para os campos mudarem quando a seleção muda

with st.form(f"editar_{k}"):
    c1, c2, c3 = st.columns(3)
    data = c1.date_input(
        "Data da inspeção", value=para_data(reg["data"], date.today()),
        format="DD/MM/YYYY", key=f"data_{k}",
    )
    obra = c2.selectbox("Obra", obras, index=posicao(obras, reg["obra"]), key=f"obra_{k}")
    local = c3.selectbox("Local", locais, index=posicao(locais, reg["local"]), key=f"local_{k}")

    c4, c5, c6 = st.columns(3)
    tipo = c4.selectbox("Tipo", tipos, index=posicao(tipos, reg["tipo"]), key=f"tipo_{k}")
    categoria = c5.selectbox(
        "Categoria", categorias, index=posicao(categorias, reg["categoria"]), key=f"cat_{k}"
    )
    gravidade = c6.selectbox(
        "Gravidade", gravidades, index=posicao(gravidades, reg["gravidade"]), key=f"grav_{k}"
    )

    c7, c8, c9 = st.columns(3)
    empreiteira = c7.selectbox(
        "Empreiteira", empreiteiras, index=posicao(empreiteiras, reg["empreiteira"]),
        key=f"emp_{k}",
    )
    responsavel = c8.text_input(
        "Responsável pela correção", value=reg["responsavel"] or "", key=f"resp_{k}"
    )
    prazo = c9.date_input(
        "Prazo para correção", value=para_data(reg["prazo"], date.today()),
        format="DD/MM/YYYY", key=f"prazo_{k}",
    )

    descricao = st.text_area(
        "Descrição do desvio *", value=reg["descricao"] or "", height=100, key=f"desc_{k}"
    )
    acao = st.text_area(
        "Ação corretiva", value=reg["acao_corretiva"] or "", height=100, key=f"acao_{k}"
    )

    c10, c11 = st.columns(2)
    status = c10.selectbox(
        "Status", STATUS, index=posicao(STATUS, reg["status"]), key=f"status_{k}"
    )
    fechamento = c11.date_input(
        "Data de fechamento (vale se o status for Concluído)",
        value=para_data(reg["data_fechamento"], date.today()),
        format="DD/MM/YYYY", key=f"fech_{k}",
    )

    salvar = st.form_submit_button("Salvar alterações", type="primary")

if salvar:
    if not descricao.strip():
        st.error("A descrição do desvio é obrigatória.")
    elif prazo < data:
        st.error("O prazo não pode ser anterior à data da inspeção.")
    elif status == "Concluído" and fechamento < data:
        st.error("A data de fechamento não pode ser anterior à data da inspeção.")
    else:
        banco.atualizar(id_sel, {
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
            "status": status,
            "data_fechamento": fechamento if status == "Concluído" else None,
        })
        st.session_state["aviso"] = ("ok", f"Desvio nº {id_sel} atualizado.")
        st.rerun()

# ---------- exclusão ----------
with st.expander("Excluir este desvio"):
    st.warning("A exclusão é definitiva e não pode ser desfeita.")
    confirma = st.checkbox("Confirmo que quero excluir este desvio", key=f"conf_{k}")
    if st.button("Excluir desvio", disabled=not confirma, key=f"del_{k}"):
        banco.excluir(id_sel)
        st.session_state["aviso"] = ("ok", f"Desvio nº {id_sel} excluído.")
        st.rerun()