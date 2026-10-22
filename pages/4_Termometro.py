from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

import banco
import termometro as tm

st.set_page_config(page_title="Termômetro de Segurança", page_icon="🌡️", layout="wide")
banco.logo_lateral()

st.title("🌡️ Termômetro de Segurança da Obra")

ss = st.session_state

# mensagem que sobrevive ao recarregamento da página
if "termo_aviso" in ss:
    tipo_aviso, texto = ss.pop("termo_aviso")
    if tipo_aviso == "ok":
        st.success(texto)
    else:
        st.error(texto)

# navegação pendente (ex.: depois de salvar, ir para a seção Ações)
if "termo_secao_pendente" in ss:
    ss["termo_secao"] = ss.pop("termo_secao_pendente")

SECOES = ["Painel", "Novo preenchimento", "Ações", "Histórico"]
secao = st.radio(
    "Seção", SECOES, horizontal=True, key="termo_secao", label_visibility="collapsed"
)
st.divider()

termo = tm.listar()
FORMATO = "DD/MM/YY"


def para_data(valor, padrao=None):
    if not valor:
        return padrao
    return pd.Timestamp(valor).date()


def posicao(itens, valor):
    return itens.index(valor) if valor in itens else 0


# =====================================================================
# PAINEL
# =====================================================================
def painel():
    if termo.empty:
        st.info("Nenhum preenchimento ainda. Use a seção Novo preenchimento.")
        return

    f1, f2 = st.columns([3, 1])
    periodo = f1.segmented_control(
        "Período",
        ["7 dias", "30 dias", "Este mês", "90 dias", "Tudo", "Personalizado"],
        default="30 dias",
        key="termo_periodo",
    ) or "30 dias"
    base = f2.segmented_control(
        "Agrupar por", ["Dia", "Semana", "Mês"], default="Semana", key="termo_base"
    ) or "Semana"

    hoje = pd.Timestamp.today().normalize()
    ultimo = max(hoje, termo["data"].max())
    if periodo == "Personalizado":
        intervalo = st.date_input(
            "Intervalo", (termo["data"].min().date(), ultimo.date()), format="DD/MM/YYYY"
        )
        if not (isinstance(intervalo, tuple) and len(intervalo) == 2):
            st.info("Escolha a data inicial e a final.")
            return
        ini, fim = pd.Timestamp(intervalo[0]), pd.Timestamp(intervalo[1])
    else:
        ini = {
            "7 dias": hoje - pd.Timedelta(days=6),
            "30 dias": hoje - pd.Timedelta(days=29),
            "90 dias": hoje - pd.Timedelta(days=89),
            "Este mês": hoje.replace(day=1),
            "Tudo": termo["data"].min(),
        }[periodo]
        fim = ultimo

    g1, g2 = st.columns(2)
    obra = g1.selectbox(
        "Obra", ["Todas"] + sorted(termo["obra"].dropna().unique()), key="termo_f_obra"
    )
    empresa = g2.selectbox(
        "Empresa", ["Todas"] + sorted(termo["empresa"].dropna().unique()), key="termo_f_emp"
    )

    df = termo[(termo["data"] >= ini) & (termo["data"] <= fim)].copy()
    if obra != "Todas":
        df = df[df["obra"] == obra]
    if empresa != "Todas":
        df = df[df["empresa"] == empresa]
    if df.empty:
        st.warning("Nenhum preenchimento para os filtros selecionados.")
        return

    # ---------- indicadores ----------
    media = df["pontuacao"].mean()
    n_alto = int((df["faixa"] == "Alto").sum())
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Preenchimentos", len(df))
    c2.metric("Pontuação média", f"{media:.1f}")
    c3.metric("Pontuação máxima", int(df["pontuacao"].max()))
    c4.metric("Faixa média", f"Risco {tm.faixa(media).lower()}")
    c5.metric("Dias de risco alto", f"{n_alto} ({100 * n_alto / len(df):.0f}%)")

    acoes_todas = tm.listar_acoes()
    acoes = acoes_todas[acoes_todas["termometro_id"].isin(df["id"])]
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Ações criadas", len(acoes))
    a2.metric("Ações em aberto", int((~acoes["fechada"]).sum()) if len(acoes) else 0)
    a3.metric("Ações vencidas", int(acoes["vencida"].sum()) if len(acoes) else 0)
    a4.metric("Ações concluídas", int(acoes["fechada"].sum()) if len(acoes) else 0)

    st.divider()

    # ---------- pontuação por período ----------
    df["periodo"] = tm.inicio_periodo(df["data"], base)
    resumo = (
        df.groupby("periodo")
        .agg(media=("pontuacao", "mean"), maxima=("pontuacao", "max"),
             preenchimentos=("id", "count"))
        .reset_index()
        .sort_values("periodo")
    )
    resumo["media"] = resumo["media"].round(1)
    resumo["rotulo"] = resumo["periodo"].map(lambda t: tm.rotulo_periodo(t, base))
    resumo["faixa"] = resumo["media"].map(tm.faixa)

    fig = px.bar(
        resumo, x="rotulo", y="media", color="faixa", text="media",
        color_discrete_map=tm.CORES,
        category_orders={"faixa": ["Baixo", "Médio", "Alto"]},
        hover_data={"maxima": True, "preenchimentos": True, "faixa": False, "rotulo": False},
        labels={"rotulo": base, "media": "Pontuação média", "maxima": "Máxima",
                "preenchimentos": "Preenchimentos"},
        title=f"Pontuação média por {base.lower()}",
    )
    fig.add_hline(y=15, line_dash="dash", line_color=tm.CORES["Médio"],
                  annotation_text="Médio a partir de 16")
    fig.add_hline(y=30, line_dash="dash", line_color=tm.CORES["Alto"],
                  annotation_text="Alto a partir de 31")
    fig.update_xaxes(type="category")
    fig.update_yaxes(range=[0, tm.PONTOS_MAX])
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver tabela por período"):
        tabela = resumo[["rotulo", "preenchimentos", "media", "maxima", "faixa"]].rename(
            columns={"rotulo": base, "preenchimentos": "Preenchimentos",
                     "media": "Média", "maxima": "Máxima", "faixa": "Faixa média"}
        )
        st.dataframe(tabela, hide_index=True, use_container_width=True)

    # ---------- faixas por obra e pontos por grupo ----------
    resp = tm.respostas_detalhadas()
    resp = resp[resp["termometro_id"].isin(df["id"]) & (resp["sim"] == 1)].copy()
    resp["grupo"] = resp["pergunta"].map(lambda n: tm.PERG[n][0])
    resp["pontos"] = resp["pergunta"].map(lambda n: tm.PERG[n][2])

    esq, dir_ = st.columns(2)
    with esq:
        por_obra = df.groupby(["obra", "faixa"]).size().reset_index(name="quantidade")
        fig = px.bar(
            por_obra, x="obra", y="quantidade", color="faixa",
            color_discrete_map=tm.CORES,
            category_orders={"faixa": ["Baixo", "Médio", "Alto"]},
            title="Preenchimentos por faixa de risco e obra",
        )
        st.plotly_chart(fig, use_container_width=True)
    with dir_:
        if resp.empty:
            st.info("Nenhum risco apontado no período.")
        else:
            por_grupo = resp.groupby("grupo")["pontos"].sum().reset_index()
            fig = px.bar(
                por_grupo.sort_values("pontos"), x="pontos", y="grupo", orientation="h",
                title="Pontos acumulados por grupo de risco",
            )
            st.plotly_chart(fig, use_container_width=True)

    # ---------- fatores de risco mais apontados ----------
    if not resp.empty:
        top = resp.groupby("pergunta").size().reset_index(name="vezes")
        top["fator"] = top["pergunta"].map(lambda n: tm.curto(n, 60))
        top["grupo"] = top["pergunta"].map(lambda n: tm.PERG[n][0])
        top = top.sort_values("vezes").tail(10)
        fig = px.bar(
            top, x="vezes", y="fator", color="grupo", orientation="h",
            title="Fatores de risco mais apontados (respostas SIM)",
            labels={"vezes": "Vezes apontado", "fator": ""},
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---------- preenchimentos de risco alto ----------
    alto = df[df["faixa"] == "Alto"].sort_values("data", ascending=False)
    st.subheader("Preenchimentos de risco alto")
    if alto.empty:
        st.success("Nenhum preenchimento de risco alto no período.")
    else:
        st.dataframe(
            alto[["id", "data", "obra", "empresa", "responsavel", "pontuacao"]],
            hide_index=True, use_container_width=True,
            column_config={
                "id": "Nº",
                "data": st.column_config.DateColumn("Data", format=FORMATO),
                "pontuacao": "Pontuação",
            },
        )


# =====================================================================
# NOVO PREENCHIMENTO
# =====================================================================
def novo():
    obras = banco.opcoes("obra")
    empresas = banco.opcoes("empreiteira")
    if not obras or not empresas:
        st.error("Cadastre pelo menos uma obra e uma empreiteira na página Configurações.")
        return

    v = ss.setdefault("termo_v", 0)  # muda após salvar, para limpar os campos

    c1, c2, c3, c4 = st.columns(4)
    data = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY", key=f"t_data_{v}")
    obra = c2.selectbox("Obra", obras, key=f"t_obra_{v}")
    empresa = c3.selectbox("Empresa", empresas, key=f"t_emp_{v}")
    responsavel = c4.text_input("Preenchido por", key=f"t_resp_{v}")

    resumo = st.container()  # preenchido depois, com o total

    st.markdown("**Marque SIM nas perguntas que se aplicam hoje:**")
    respostas = {}
    esq, dir_ = st.columns(2)
    for i, grupo in enumerate(tm.GRUPOS):
        with (esq if i < 2 else dir_):
            st.markdown(f"##### {grupo}")
            for n, g, texto, pts in tm.PERGUNTAS:
                if g == grupo:
                    sufixo = "pt" if pts == 1 else "pts"
                    respostas[n] = st.checkbox(
                        f"{n}. {texto}  ({pts} {sufixo})", key=f"t_q{n}_{v}"
                    )

    obs = st.text_area("Observações (opcional)", key=f"t_obs_{v}")

    total = tm.calcular(respostas)
    fx = tm.faixa(total)
    with resumo:
        m1, m2 = st.columns([1, 3])
        m1.metric("Pontuação", f"{total} / {tm.PONTOS_MAX}")
        mensagem = f"Risco {fx.lower()}: {tm.SIGNIFICADO[fx]}"
        with m2:
            if fx == "Baixo":
                st.success(mensagem)
            elif fx == "Médio":
                st.warning(mensagem)
            else:
                st.error(mensagem)

    if st.button("Salvar preenchimento", type="primary", key=f"t_salvar_{v}"):
        novo_id = tm.salvar(data, obra, empresa, responsavel.strip(), respostas, obs.strip())
        ss["termo_v"] = v + 1
        if total > 0:
            ss["termo_foco"] = novo_id
            ss["termo_secao_pendente"] = "Ações"
            ss["termo_aviso"] = (
                "ok",
                f"Preenchimento nº {novo_id} salvo ({total} pontos, risco {fx.lower()}). "
                "Crie abaixo as ações para os desvios apontados.",
            )
        else:
            ss["termo_aviso"] = ("ok", f"Preenchimento nº {novo_id} salvo (0 pontos).")
        st.rerun()


# =====================================================================
# AÇÕES
# =====================================================================
def acoes_secao():
    if termo.empty:
        st.info("Nenhum preenchimento ainda. Use a seção Novo preenchimento.")
        return

    st.subheader("Nova ação")
    info = termo.set_index("id")
    ids = termo.sort_values(["data", "id"], ascending=False)["id"].tolist()

    def rotulo(i):
        r = info.loc[i]
        return (f"Nº {i} · {r['data']:%d/%m/%y} · {r['obra']} · {r['empresa']} · "
                f"{r['pontuacao']} pts ({r['faixa']})")

    if "termo_foco" in ss:
        ss["termo_prenc"] = ss.pop("termo_foco")
    if ss.get("termo_prenc") not in ids:
        ss.pop("termo_prenc", None)
    sel = st.selectbox("Preenchimento", ids, format_func=rotulo, key="termo_prenc")

    sim = tm.respostas_sim(sel)
    todas = tm.listar_acoes()
    if not sim:
        st.info("Este preenchimento não apontou riscos (nenhuma resposta SIM).")
    else:
        do_prenc = todas[todas["termometro_id"] == sel]
        contagem = do_prenc.groupby("pergunta").size() if len(do_prenc) else pd.Series(dtype=int)
        st.dataframe(
            [{"Nº": n, "Desvio apontado": tm.PERG[n][1], "Pontos": tm.PERG[n][2],
              "Ações criadas": int(contagem.get(n, 0))} for n in sim],
            hide_index=True, use_container_width=True,
        )
        with st.form("nova_acao", clear_on_submit=True):
            pergunta = st.selectbox(
                "Desvio apontado", sim, format_func=lambda n: f"{n}. {tm.PERG[n][1]}"
            )
            acao = st.text_area("Ação a ser tomada *", height=100)
            c1, c2 = st.columns(2)
            responsavel = c1.text_input("Responsável")
            prazo = c2.date_input(
                "Prazo", value=date.today() + timedelta(days=3), format="DD/MM/YYYY"
            )
            criar = st.form_submit_button("Criar ação", type="primary")
        if criar:
            if not acao.strip():
                st.error("Descreva a ação a ser tomada. Preencha os campos novamente.")
            else:
                tm.criar_acao(sel, pergunta, acao.strip(), responsavel.strip(), prazo)
                ss["termo_aviso"] = ("ok", "Ação criada.")
                st.rerun()

    # ---------- acompanhamento ----------
    st.divider()
    st.subheader("Acompanhamento das ações")
    if todas.empty:
        st.info("Nenhuma ação criada ainda.")
        return

    f1, f2 = st.columns(2)
    situacao = f1.segmented_control(
        "Situação", ["Em aberto", "Vencidas", "Concluídas", "Todas"],
        default="Em aberto", key="termo_sit",
    ) or "Em aberto"
    obra_f = f2.selectbox(
        "Obra", ["Todas"] + sorted(todas["obra"].dropna().unique()), key="termo_acao_obra"
    )

    df = todas
    if situacao == "Em aberto":
        df = df[~df["fechada"]]
    elif situacao == "Vencidas":
        df = df[df["vencida"]]
    elif situacao == "Concluídas":
        df = df[df["fechada"]]
    if obra_f != "Todas":
        df = df[df["obra"] == obra_f]
    if df.empty:
        st.success("Nenhuma ação nesta situação.")
        return

    df = df.sort_values("prazo") if situacao in ("Em aberto", "Vencidas") \
        else df.sort_values("id", ascending=False)
    tabela = df[["id", "data_preenchimento", "obra", "empresa", "desvio", "acao",
                 "responsavel", "prazo", "situacao"]].reset_index(drop=True)

    st.markdown(f"**{len(tabela)}** ação(ões). Clique em uma linha para abrir.")
    evento = st.dataframe(
        tabela, hide_index=True, use_container_width=True,
        on_select="rerun", selection_mode="single-row", key="termo_tab_acoes",
        column_config={
            "id": "Nº",
            "data_preenchimento": st.column_config.DateColumn("Data", format=FORMATO),
            "desvio": "Desvio apontado",
            "acao": "Ação",
            "prazo": st.column_config.DateColumn("Prazo", format=FORMATO),
            "situacao": "Situação",
        },
    )
    linhas = evento.selection.rows
    if not linhas:
        st.info("Selecione uma ação na tabela para concluir, editar ou excluir.")
        return

    aid = int(tabela.iloc[linhas[0]]["id"])
    reg = tm.obter_acao(aid)
    if not reg:
        st.error("Ação não encontrada. Atualize a página.")
        return

    st.markdown(f"##### Ação nº {aid}")
    if not reg["status"].lower().startswith("conclu"):
        if st.button("✅ Marcar como concluída hoje", type="primary", key=f"a_rapido_{aid}"):
            tm.atualizar_acao(aid, reg["acao"], reg["responsavel"],
                              para_data(reg["prazo"]), "Concluída", date.today())
            ss["termo_aviso"] = ("ok", f"Ação nº {aid} concluída.")
            st.rerun()

    STATUS = ["Aberta", "Concluída"]
    with st.form(f"a_editar_{aid}"):
        acao_e = st.text_area("Ação", value=reg["acao"] or "", height=100, key=f"a_acao_{aid}")
        c1, c2, c3 = st.columns(3)
        resp_e = c1.text_input("Responsável", value=reg["responsavel"] or "", key=f"a_resp_{aid}")
        prazo_e = c2.date_input(
            "Prazo", value=para_data(reg["prazo"], date.today()),
            format="DD/MM/YYYY", key=f"a_prazo_{aid}",
        )
        status_e = c3.selectbox(
            "Status", STATUS,
            index=1 if reg["status"].lower().startswith("conclu") else 0,
            key=f"a_status_{aid}",
        )
        fech_e = st.date_input(
            "Data de conclusão (vale se o status for Concluída)",
            value=para_data(reg["data_fechamento"], date.today()),
            format="DD/MM/YYYY", key=f"a_fech_{aid}",
        )
        salvar = st.form_submit_button("Salvar alterações", type="primary")
    if salvar:
        if not acao_e.strip():
            st.error("A descrição da ação é obrigatória.")
        else:
            tm.atualizar_acao(aid, acao_e.strip(), resp_e.strip(), prazo_e, status_e,
                              fech_e if status_e == "Concluída" else None)
            ss["termo_aviso"] = ("ok", f"Ação nº {aid} atualizada.")
            st.rerun()

    with st.expander("Excluir esta ação"):
        st.warning("A exclusão é definitiva e não pode ser desfeita.")
        conf = st.checkbox("Confirmo que quero excluir esta ação", key=f"a_conf_{aid}")
        if st.button("Excluir ação", disabled=not conf, key=f"a_del_{aid}"):
            tm.excluir_acao(aid)
            ss["termo_aviso"] = ("ok", f"Ação nº {aid} excluída.")
            st.rerun()


# =====================================================================
# HISTÓRICO
# =====================================================================
def historico():
    if termo.empty:
        st.info("Nenhum preenchimento ainda. Use a seção Novo preenchimento.")
        return

    obra_f = st.selectbox(
        "Obra", ["Todas"] + sorted(termo["obra"].dropna().unique()), key="termo_h_obra"
    )
    df = termo if obra_f == "Todas" else termo[termo["obra"] == obra_f]
    df = df.sort_values(["data", "id"], ascending=False)
    tabela = df[["id", "data", "obra", "empresa", "responsavel", "pontuacao", "faixa"]] \
        .reset_index(drop=True)

    st.markdown(f"**{len(tabela)}** preenchimento(s). Clique em uma linha para ver os detalhes.")
    evento = st.dataframe(
        tabela, hide_index=True, use_container_width=True,
        on_select="rerun", selection_mode="single-row", key="termo_tab_hist",
        column_config={
            "id": "Nº",
            "data": st.column_config.DateColumn("Data", format=FORMATO),
            "pontuacao": "Pontuação",
            "faixa": "Faixa",
        },
    )
    linhas = evento.selection.rows
    if not linhas:
        st.info("Selecione um preenchimento na tabela.")
        return

    tid = int(tabela.iloc[linhas[0]]["id"])
    linha = tabela.iloc[linhas[0]]
    sim = tm.respostas_sim(tid)

    st.divider()
    st.subheader(f"Preenchimento nº {tid}")
    st.markdown(
        f"**{linha['data']:%d/%m/%Y}** · {linha['obra']} · {linha['empresa']} · "
        f"**{linha['pontuacao']} pontos** (risco {linha['faixa'].lower()})"
    )
    st.dataframe(
        [{"Nº": n, "Grupo": g, "Pergunta": texto, "Pontos": pts,
          "Resposta": "SIM" if n in sim else "NÃO"} for n, g, texto, pts in tm.PERGUNTAS],
        hide_index=True, use_container_width=True,
    )

    acoes = tm.listar_acoes()
    acoes = acoes[acoes["termometro_id"] == tid]
    if len(acoes):
        st.markdown("**Ações deste preenchimento**")
        st.dataframe(
            acoes[["id", "desvio", "acao", "responsavel", "prazo", "situacao"]],
            hide_index=True, use_container_width=True,
            column_config={
                "id": "Nº", "desvio": "Desvio apontado", "acao": "Ação",
                "prazo": st.column_config.DateColumn("Prazo", format=FORMATO),
                "situacao": "Situação",
            },
        )

    with st.expander("Excluir este preenchimento"):
        st.warning(
            "A exclusão é definitiva e apaga também as ações vinculadas a este preenchimento."
        )
        conf = st.checkbox("Confirmo que quero excluir", key=f"h_conf_{tid}")
        if st.button("Excluir preenchimento", disabled=not conf, key=f"h_del_{tid}"):
            tm.excluir(tid)
            ss["termo_aviso"] = ("ok", f"Preenchimento nº {tid} excluído.")
            st.rerun()


# =====================================================================
if secao == "Painel":
    painel()
elif secao == "Novo preenchimento":
    novo()
elif secao == "Ações":
    acoes_secao()
else:
    historico()