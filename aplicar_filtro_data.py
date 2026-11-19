"""Acrescenta o filtro por data da avaliação ao Quadro da página Avaliação de Empresas.

Execute uma vez, na pasta do projeto:  python aplicar_filtro_data.py
Antes de alterar cada arquivo, o script guarda uma cópia com final .bak.
"""
from pathlib import Path

NOVAS_FUNCOES = '''def datas_do_mes(df: pd.DataFrame, obra: str, mes) -> list:
    """Datas (a mais recente primeiro) em que houve avaliação na obra e no mês."""
    d = df[(df["obra"] == obra) & (df["mes_ref"] == pd.Timestamp(mes))]
    return [pd.Timestamp(x) for x in sorted(d["data"].dt.normalize().unique(), reverse=True)]


def contagem_por_data(df: pd.DataFrame, obra: str, mes) -> dict:
    """Quantidade de empresas avaliadas em cada data da obra e do mês."""
    d = df[(df["obra"] == obra) & (df["mes_ref"] == pd.Timestamp(mes))]
    return {pd.Timestamp(k): int(v) for k, v in d.groupby(d["data"].dt.normalize())["empresa"].nunique().items()}


def linhas_quadro(df: pd.DataFrame, obra: str, mes, dia=None) -> list:
    """Uma linha por empresa, na ordem em que as empresas foram avaliadas.

    Com dia, usa só as avaliações daquela data. Sem dia, usa a mais recente de cada empresa no mês.
    """
    d = df[(df["obra"] == obra) & (df["mes_ref"] == pd.Timestamp(mes))]
    if dia is not None:
        d = d[d["data"].dt.normalize() == pd.Timestamp(dia).normalize()]
    if d.empty:
        return []
    ordem = d.groupby("empresa")["id"].min().sort_values().index.tolist()
    linhas = []
    for emp in ordem:
        g = d[d["empresa"] == emp].sort_values(["data", "id"]).iloc[-1]
        linhas.append({"empresa": emp, "data": g["data"], "id": int(g["id"]),
                       **{c: g[c] for c in COLUNAS_CRIT}})
    return linhas


'''

NOVO_QUADRO = '''def quadro():
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


'''


def ler(caminho):
    p = Path(caminho)
    if not p.exists():
        print(f"[ERRO] {caminho} não encontrado. Rode o script dentro da pasta do projeto (C:\\painel_sso).")
        return None, None
    return p, p.read_text(encoding="utf-8")


def gravar(p, texto_antigo, texto_novo):
    Path(str(p) + ".bak").write_text(texto_antigo, encoding="utf-8")
    p.write_text(texto_novo, encoding="utf-8")
    print(f"[OK] {p} atualizado (cópia de segurança: {p.name}.bak).")


# ---------- avaliacoes.py
p, s = ler("avaliacoes.py")
if p:
    if "def datas_do_mes(" in s:
        print("[OK] avaliacoes.py já estava atualizado.")
    elif s.count("def linhas_quadro(") == 1 and s.count("def notas_por_criterio(") == 1:
        i, j = s.index("def linhas_quadro("), s.index("def notas_por_criterio(")
        gravar(p, s, s[:i] + NOVAS_FUNCOES + s[j:])
    else:
        print("[ERRO] avaliacoes.py: não encontrei o ponto de troca. Este arquivo NÃO foi alterado.")

# ---------- página
p, s = ler("pages/5_Avaliacao_de_Empresas.py")
if p:
    marca_quadro = "# NOVA AVALIAÇÃO"
    chave = "ss[\"aval_q_pend\"] = (obra, mes)"
    if "MES_INTEIRO" in s:
        print("[OK] pages/5_Avaliacao_de_Empresas.py já estava atualizado.")
    elif (s.count("def quadro():") == 1 and s.count(chave) == 1 and s.count('FORMATO = "DD/MM/YY"') == 1
          and s.count("# =====================================================================\n" + marca_quadro) == 1):
        i = s.index("def quadro():")
        j = s.index("# =====================================================================\n" + marca_quadro)
        novo = s[:i] + NOVO_QUADRO + s[j:]
        novo = novo.replace(chave, 'ss["aval_q_pend"] = (obra, mes, pd.Timestamp(data).normalize())', 1)
        novo = novo.replace('FORMATO = "DD/MM/YY"', 'FORMATO = "DD/MM/YY"\nMES_INTEIRO = "Mês inteiro"', 1)
        gravar(p, s, novo)
    else:
        print("[ERRO] pages/5_Avaliacao_de_Empresas.py: não encontrei o ponto de troca. Este arquivo NÃO foi alterado.")