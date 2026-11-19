from datetime import date

import pandas as pd
import streamlit as st

import avaliacoes as av
import banco
import graficos

st.set_page_config(page_title="Avaliação de Empresas", page_icon="📋", layout="wide")
banco.logo_lateral()

st.title("📋 Avaliação de Empresas")
st.caption(
    "Gestão visual das empresas contratadas: serviço, segurança, qualidade, "
    "organização, prazo e desperdício."
)

ss = st.session_state

# mensagem que sobrevive ao recarregamento da página
if "aval_aviso" in ss:
    tipo_aviso, texto = ss.pop("aval_aviso")
    if tipo_aviso == "ok":
        st.success(texto)
    else:
        st.error(texto)

# navegação pendente (ex.: depois de salvar, ir para o Quadro)
if "aval_secao_pendente" in ss:
    ss["aval_secao"] = ss.pop("aval_secao_pendente")

SECOES = ["Quadro", "Nova avaliação", "Histórico", "Indicadores"]
secao = st.radio(
    "Seção", SECOES, horizontal=True, key="aval_secao", label_visibility="collapsed"
)
st.divider()

dados = av.listar()
FORMATO = "DD/MM/YY"
MES_INTEIRO = "Mês inteiro"


def seletor_notas(prefixo, padrao=None):
    """Seis seletores de nota (Bom, Regular, Ruim), um por critério."""
    padrao = padrao or {}
    notas = {}
    esq, dir_ = st.columns(2)
    for i, (chave, rotulo) in enumerate(av.CRITERIOS):
        with (esq if i < 3 else dir_):
            notas[chave] = st.segmented_control(
                rotulo, av.NOTAS, default=padrao.get(chave),
                format_func=lambda n: av.ROTULO_NOTA[n], key=f"{prefixo}_{chave}",
            )
    return notas


def com_atual(lista, atual):
    itens = banco.opcoes(lista)
    if atual and atual not in itens:
        itens = itens + [atual]
    return itens


def posicao(itens, valor):
    return itens.index(valor) if valor in itens else 0


# =====================================================================
# QUADRO
# =====================================================================
def quadro():
    if dados.empty:
        st.info("Nenhuma avaliação registrada ainda. Use a seção Nova avaliação.")
        return

    # depois de salvar, abre o quadro da obra, do mês e da data avaliados
    if "aval_q_pend" in ss:
        obra_p, mes_p, dia_p = ss.pop("aval_q_pend")
        ss["aval_q_obra"] = obra_p
        ss["aval_q_mes"] = mes_p
        ss["aval_q_data"] = dia_p

    obras = sorted(dados["obra"].dropna().unique())
    if ss.get("aval_q_obra") not in obras:
        ss.pop("aval_q_obra", None)
    c1, c2, c3 = st.columns(3)
    obra = c1.selectbox("Obra", obras, key="aval_q_obra")

    meses = [pd.Timestamp(m) for m in sorted(dados[dados["obra"] == obra]["mes_ref"].unique(), reverse=True)]
    if ss.get("aval_q_mes") not in meses:
        ss.pop("aval_q_mes", None)
    mes = c2.selectbox("Mês", meses, format_func=av.rotulo_mes, key="aval_q_mes")

    contagem = av.contagem_por_data(dados, obra, mes)
    opcoes_data = av.datas_do_mes(dados, obra, mes) + [MES_INTEIRO]
    if ss.get("aval_q_data") not in opcoes_data:
        ss.pop("aval_q_data", None)

    def rotulo_data(d):
        if isinstance(d, str):
            return "Mês inteiro (a mais recente de cada empresa)"
        return f"{d:%d/%m/%Y}  ({contagem[d]} empresa(s))"

    dia = c3.selectbox("Data da avaliação", opcoes_data, format_func=rotulo_data, key="aval_q_data")
    filtro_dia = None if isinstance(dia, str) else dia

    linhas = av.linhas_quadro(dados, obra, mes, filtro_dia)
    data_ref = filtro_dia if filtro_dia is not None else max(l["data"] for l in linhas)
    titulo = f"{av.MESES[mes.month - 1].upper()}  {data_ref:%d/%m/%y}"
    st.markdown(av.html_quadro(linhas, titulo), unsafe_allow_html=True)
    if filtro_dia is not None:
        st.caption(f"{len(linhas)} empresa(s) avaliada(s) em {filtro_dia:%d/%m/%Y}.")
    else:
        st.caption(
            f"{len(linhas)} empresa(s) avaliada(s) no mês. Quando uma empresa tem mais de uma avaliação, "
            "o quadro mostra a mais recente. Para ver só uma data, escolha-a em Data da avaliação."
        )

    with st.expander("Ver a pontuação"):
        pontos = dados[dados["id"].isin([l["id"] for l in linhas])][["empresa", "data", "pontos", "pct"]]
        st.dataframe(
            pontos.rename(columns={"empresa": "Empresa", "data": "Data", "pontos": "Pontos", "pct": "Pontuação"}),
            hide_index=True, width="stretch",
            column_config={
                "Data": st.column_config.DateColumn("Data", format=FORMATO),
                "Pontuação": st.column_config.NumberColumn("Pontuação", format="%d%%"),
            },
        )
        st.caption("Bom vale 2 pontos, Regular 1 e Ruim 0. A pontuação considera só os critérios avaliados; 100% significa todas as notas Bom.")


# =====================================================================
# NOVA AVALIAÇÃO
# =====================================================================
def nova():
    obras = banco.opcoes("obra")
    empresas = banco.opcoes("empreiteira")
    if not obras or not empresas:
        st.error("Cadastre pelo menos uma obra e uma empreiteira na página Configurações.")
        return

    v = ss.setdefault("aval_v", 0)  # muda após salvar, para limpar os campos

    c1, c2, c3 = st.columns(3)
    data = c1.date_input("Data da avaliação", value=date.today(), format="DD/MM/YYYY", key=f"aval_data_{v}")
    obra = c2.selectbox("Obra", obras, key=f"aval_obra_{v}")
    empresa = c3.selectbox("Empresa", empresas, key=f"aval_emp_{v}")

    mes = pd.Timestamp(data).to_period("M").start_time
    ja = dados[(dados["obra"] == obra) & (dados["empresa"] == empresa) & (dados["mes_ref"] == mes)]
    if not ja.empty:
        st.info(
            f"Esta empresa já tem {len(ja)} avaliação(ões) em {av.rotulo_mes(mes)}. "
            "A nova passa a ser a mais recente no quadro; as anteriores ficam no histórico."
        )

    st.markdown("**Notas por critério**")
    notas = seletor_notas(f"aval_n_{v}")

    c4, c5 = st.columns([1, 2])
    avaliador = c4.text_input("Avaliador (opcional)", key=f"aval_av_{v}")
    obs = c5.text_area("Observações (opcional)", height=80, key=f"aval_obs_{v}")

    escolhidas = [n for n in notas.values() if n]
    if escolhidas:
        total = sum(av.PONTOS[n] for n in escolhidas)
        st.metric("Pontuação desta avaliação", f"{100 * total / (2 * len(escolhidas)):.0f}%")
        st.caption(
            f"{len(escolhidas)} de {len(av.CRITERIOS)} critérios avaliados. "
            "Os critérios sem nota ficam em branco no quadro."
        )

    if st.button("Salvar avaliação", type="primary", key=f"aval_salvar_{v}"):
        if not escolhidas:
            st.error("Escolha a nota de pelo menos um critério.")
        else:
            av.salvar(data, obra, empresa, notas, avaliador.strip(), obs.strip())
            ss["aval_v"] = v + 1
            ss["aval_secao_pendente"] = "Quadro"
            ss["aval_q_pend"] = (obra, mes, pd.Timestamp(data).normalize())
            ss["aval_aviso"] = ("ok", f"Avaliação de {empresa} salva.")
            st.rerun()


# =====================================================================
# HISTÓRICO
# =====================================================================
def historico():
    if dados.empty:
        st.info("Nenhuma avaliação registrada ainda. Use a seção Nova avaliação.")
        return

    f1, f2, f3 = st.columns(3)
    obra_f = f1.selectbox("Obra", ["Todas"] + sorted(dados["obra"].unique()), key="aval_h_obra")
    emp_f = f2.selectbox("Empresa", ["Todas"] + sorted(dados["empresa"].unique()), key="aval_h_emp")
    meses = [pd.Timestamp(m) for m in sorted(dados["mes_ref"].unique(), reverse=True)]
    mes_f = f3.selectbox(
        "Mês", ["Todos"] + meses,
        format_func=lambda m: m if isinstance(m, str) else av.rotulo_mes(m), key="aval_h_mes",
    )

    df = dados
    if obra_f != "Todas":
        df = df[df["obra"] == obra_f]
    if emp_f != "Todas":
        df = df[df["empresa"] == emp_f]
    if not isinstance(mes_f, str):
        df = df[df["mes_ref"] == mes_f]
    if df.empty:
        st.warning("Nenhuma avaliação para os filtros escolhidos.")
        return
    df = df.sort_values(["data", "id"], ascending=False).reset_index(drop=True)

    tabela = df[["id", "data", "obra", "empresa"] + av.COLUNAS_CRIT + ["pct"]].copy()
    for c in av.COLUNAS_CRIT:
        tabela[c] = tabela[c].map(av.EMOJI)
    config = {
        "id": "Nº",
        "data": st.column_config.DateColumn("Data", format=FORMATO),
        "pct": st.column_config.NumberColumn("Pontuação", format="%d%%"),
    }
    config.update({c: av.ROTULO_CRIT[c] for c in av.COLUNAS_CRIT})
    st.markdown(f"**{len(tabela)}** avaliação(ões). Clique em uma linha para editar ou excluir.")
    evento = st.dataframe(
        tabela, hide_index=True, width="stretch", on_select="rerun",
        selection_mode="single-row", key="aval_tab", column_config=config,
    )
    linhas = evento.selection.rows
    if not linhas:
        st.info("Selecione uma avaliação na tabela.")
        return

    reg = df.iloc[linhas[0]]
    aid = int(reg["id"])
    st.divider()
    st.subheader(f"Avaliação nº {aid}")
    obras = com_atual("obra", reg["obra"])
    empresas = com_atual("empreiteira", reg["empresa"])

    with st.form(f"aval_editar_{aid}"):
        c1, c2, c3 = st.columns(3)
        data_e = c1.date_input("Data da avaliação", value=reg["data"].date(), format="DD/MM/YYYY", key=f"aval_e_data_{aid}")
        obra_e = c2.selectbox("Obra", obras, index=posicao(obras, reg["obra"]), key=f"aval_e_obra_{aid}")
        emp_e = c3.selectbox("Empresa", empresas, index=posicao(empresas, reg["empresa"]), key=f"aval_e_emp_{aid}")
        notas_e = seletor_notas(
            f"aval_e_{aid}", {c: (reg[c] if isinstance(reg[c], str) else None) for c in av.COLUNAS_CRIT}
        )
        c4, c5 = st.columns([1, 2])
        avaliador_e = c4.text_input("Avaliador", value=reg["avaliador"] or "", key=f"aval_e_av_{aid}")
        obs_e = c5.text_area("Observações", value=reg["observacao"] or "", height=80, key=f"aval_e_obs_{aid}")
        salvar = st.form_submit_button("Salvar alterações", type="primary")
    if salvar:
        if all(n is None for n in notas_e.values()):
            st.error("Escolha a nota de pelo menos um critério.")
        else:
            av.atualizar(aid, data_e, obra_e, emp_e, notas_e, avaliador_e.strip(), obs_e.strip())
            ss["aval_aviso"] = ("ok", f"Avaliação nº {aid} atualizada.")
            st.rerun()

    with st.expander("Excluir esta avaliação"):
        st.warning("A exclusão é definitiva e não pode ser desfeita.")
        conf = st.checkbox("Confirmo que quero excluir esta avaliação", key=f"aval_conf_{aid}")
        if st.button("Excluir avaliação", disabled=not conf, key=f"aval_del_{aid}"):
            av.excluir(aid)
            ss["aval_aviso"] = ("ok", f"Avaliação nº {aid} excluída.")
            st.rerun()


# =====================================================================
# INDICADORES
# =====================================================================
def indicadores():
    if dados.empty:
        st.info("Nenhuma avaliação registrada ainda. Use a seção Nova avaliação.")
        return

    f1, f2 = st.columns([1, 2])
    obra_f = f1.selectbox("Obra", ["Todas"] + sorted(dados["obra"].unique()), key="aval_i_obra")
    periodo = f2.segmented_control(
        "Período", ["3 meses", "6 meses", "12 meses", "Tudo"], default="6 meses", key="aval_i_per",
    ) or "6 meses"

    df = dados if obra_f == "Todas" else dados[dados["obra"] == obra_f]
    if periodo != "Tudo":
        n = int(periodo.split()[0])
        limite = pd.Timestamp.today().normalize().replace(day=1) - pd.DateOffset(months=n - 1)
        df = df[df["data"] >= limite]
    if df.empty:
        st.warning("Nenhuma avaliação no período escolhido.")
        return

    todas = pd.concat([df[c] for c in av.COLUNAS_CRIT])
    pct_notas = todas.value_counts(normalize=True) * 100
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Avaliações", len(df))
    k2.metric("Empresas avaliadas", df["empresa"].nunique())
    k3.metric("Notas Bom", f"{pct_notas.get('Bom', 0):.0f}%")
    k4.metric("Notas Regular", f"{pct_notas.get('Regular', 0):.0f}%")
    k5.metric("Notas Ruim", f"{pct_notas.get('Ruim', 0):.0f}%")
    st.divider()

    esq, dir_ = st.columns(2)
    with esq:
        pe = av.pontuacao_por_empresa(df)
        fig = graficos.barras(
            pe, x="pct", y="empresa", orientation="h",
            labels={"pct": "Pontuação média (%)", "empresa": ""},
            title="Pontuação média por empresa (%)",
        )
        fig.update_xaxes(range=[0, 100])
        st.plotly_chart(fig, width="stretch")
    with dir_:
        npc = av.notas_por_criterio(df)
        fig = graficos.barras(
            npc, x="criterio", y="quantidade", color="nota", color_discrete_map=av.CORES,
            category_orders={"nota": av.NOTAS, "criterio": [av.ROTULO_CRIT[c] for c in av.COLUNAS_CRIT]},
            labels={"criterio": "", "quantidade": "Notas", "nota": "Nota"},
            title="Notas por critério",
        )
        st.plotly_chart(fig, width="stretch")

    pm = av.pontuacao_por_mes(df)
    fig = graficos.barras(
        pm, x="rotulo", y="pct", labels={"rotulo": "Mês", "pct": "Pontuação média (%)"},
        title="Evolução mensal da pontuação média (%)",
    )
    fig.update_xaxes(type="category")
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, width="stretch")
    st.caption("Pontuação: Bom vale 2 pontos, Regular 1 e Ruim 0. Cem por cento significa todas as notas Bom.")


# =====================================================================
if secao == "Quadro":
    quadro()
elif secao == "Nova avaliação":
    nova()
elif secao == "Histórico":
    historico()
else:
    indicadores()