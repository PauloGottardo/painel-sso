"""Avaliação de empresas contratadas (quadro de gestão visual): critérios, notas, banco e quadro em HTML."""
import base64
from contextlib import closing
from html import escape

import pandas as pd

import banco

CRITERIOS = [
    ("servico", "Serviço"),
    ("seguranca", "Segurança"),
    ("qualidade", "Qualidade"),
    ("organizacao", "Organização"),
    ("prazo", "Prazo"),
    ("desperdicio", "Desperdício"),
]
COLUNAS_CRIT = [c for c, _ in CRITERIOS]
ROTULO_CRIT = dict(CRITERIOS)
NOTAS = ["Bom", "Regular", "Ruim"]
PONTOS = {"Bom": 2, "Regular": 1, "Ruim": 0}
PONTOS_MAX = 2 * len(CRITERIOS)
EMOJI = {"Bom": "😊", "Regular": "😬", "Ruim": "😡"}
ROTULO_NOTA = {n: f"{EMOJI[n]} {n}" for n in NOTAS}
CORES = {"Bom": "#2E7D32", "Regular": "#F9A825", "Ruim": "#C62828"}
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]


# ---------------------------------------------------------------- banco de dados
def conectar():
    con = banco.conectar()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS avaliacoes_empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            obra TEXT NOT NULL,
            empresa TEXT NOT NULL,
            servico TEXT,
            seguranca TEXT,
            qualidade TEXT,
            organizacao TEXT,
            prazo TEXT,
            desperdicio TEXT,
            avaliador TEXT,
            observacao TEXT
        )
        """
    )
    con.commit()
    return con


def _validar(notas: dict) -> None:
    for c in COLUNAS_CRIT:
        if notas.get(c) is not None and notas.get(c) not in NOTAS:
            raise ValueError(f"Nota inválida em {ROTULO_CRIT[c]}.")
    if all(notas.get(c) is None for c in COLUNAS_CRIT):
        raise ValueError("Informe a nota de pelo menos um critério.")


def salvar(data, obra, empresa, notas, avaliador="", observacao="") -> int:
    _validar(notas)
    with closing(conectar()) as con:
        cur = con.execute(
            "INSERT INTO avaliacoes_empresas "
            "(data, obra, empresa, servico, seguranca, qualidade, organizacao, prazo, desperdicio, avaliador, observacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (banco._iso(data), obra, empresa, *[notas.get(c) for c in COLUNAS_CRIT], avaliador, observacao),
        )
        con.commit()
        return cur.lastrowid


def atualizar(av_id, data, obra, empresa, notas, avaliador="", observacao="") -> None:
    _validar(notas)
    with closing(conectar()) as con:
        con.execute(
            "UPDATE avaliacoes_empresas SET data = ?, obra = ?, empresa = ?, servico = ?, seguranca = ?, "
            "qualidade = ?, organizacao = ?, prazo = ?, desperdicio = ?, avaliador = ?, observacao = ? WHERE id = ?",
            (banco._iso(data), obra, empresa, *[notas.get(c) for c in COLUNAS_CRIT], avaliador, observacao, av_id),
        )
        con.commit()


def excluir(av_id: int) -> None:
    with closing(conectar()) as con:
        con.execute("DELETE FROM avaliacoes_empresas WHERE id = ?", (av_id,))
        con.commit()


def listar() -> pd.DataFrame:
    with closing(conectar()) as con:
        df = pd.read_sql_query("SELECT * FROM avaliacoes_empresas", con)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["mes_ref"] = df["data"].dt.to_period("M").dt.start_time
    if len(df):
        df["pontos"] = sum(df[c].map(PONTOS).fillna(0) for c in COLUNAS_CRIT)
        df["criterios"] = sum(df[c].isin(NOTAS).astype(int) for c in COLUNAS_CRIT)  # critérios avaliados
        df["pct"] = (df["pontos"] / (2 * df["criterios"]) * 100).round(0)
    else:
        for col in ("pontos", "criterios", "pct"):
            df[col] = pd.Series(dtype=float)
    return df


def rotulo_mes(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"{MESES[ts.month - 1]}/{ts.year}"


# ---------------------------------------------------------------- dados para o quadro e os gráficos
def datas_do_mes(df: pd.DataFrame, obra: str, mes) -> list:
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


def notas_por_criterio(df: pd.DataFrame) -> pd.DataFrame:
    """Quantidade de cada nota por critério (formato longo, para gráfico)."""
    linhas = []
    for c in COLUNAS_CRIT:
        cont = df[c].value_counts()
        for n in NOTAS:
            linhas.append({"criterio": ROTULO_CRIT[c], "nota": n, "quantidade": int(cont.get(n, 0))})
    return pd.DataFrame(linhas)


def pontuacao_por_empresa(df: pd.DataFrame) -> pd.DataFrame:
    r = df.groupby("empresa").agg(pct=("pct", "mean"), avaliacoes=("id", "count")).reset_index()
    r["pct"] = r["pct"].round(0)
    return r.sort_values("pct")


def pontuacao_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    r = df.groupby("mes_ref").agg(pct=("pct", "mean")).reset_index().sort_values("mes_ref")
    r["pct"] = r["pct"].round(0)
    r["rotulo"] = r["mes_ref"].map(lambda m: f"{pd.Timestamp(m).month:02d}/{pd.Timestamp(m).year}")
    return r


# ---------------------------------------------------------------- rostos e quadro em HTML
def _svg_rosto(nota: str) -> str:
    """Rosto colorido (verde, amarelo ou vermelho) como imagem SVG embutida."""
    olhos = '<circle cx="35" cy="42" r="5.5" fill="#1F2937"/><circle cx="65" cy="42" r="5.5" fill="#1F2937"/>'
    if nota == "Bom":
        fundo, borda = "#43A047", "#2E7D32"
        resto = '<path d="M28 58 Q50 84 72 58" stroke="#1F2937" stroke-width="5.5" fill="none" stroke-linecap="round"/>'
    elif nota == "Regular":
        fundo, borda = "#F9A825", "#C77700"
        resto = (
            '<rect x="27" y="60" width="46" height="17" rx="7" fill="#FFFFFF" stroke="#1F2937" stroke-width="4"/>'
            '<path d="M38.5 60 V77 M50 60 V77 M61.5 60 V77 M27 68.5 H73" stroke="#1F2937" stroke-width="2.5" fill="none"/>'
        )
    else:
        fundo, borda = "#E53935", "#B71C1C"
        olhos = '<circle cx="36" cy="48" r="5.5" fill="#1F2937"/><circle cx="64" cy="48" r="5.5" fill="#1F2937"/>'
        resto = (
            '<path d="M22 30 L44 41 M78 30 L56 41" stroke="#1F2937" stroke-width="6" stroke-linecap="round"/>'
            '<path d="M30 76 Q50 56 70 76" stroke="#1F2937" stroke-width="5.5" fill="none" stroke-linecap="round"/>'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<circle cx="50" cy="50" r="46" fill="{fundo}" stroke="{borda}" stroke-width="5"/>{olhos}{resto}</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _img(nota: str, tam: int) -> str:
    return f'<img src="{_svg_rosto(nota)}" width="{tam}" height="{tam}" style="display:inline-block;vertical-align:middle"/>'


def html_quadro(linhas: list, titulo_mes: str, total_linhas: int = 10) -> str:
    """Recria o quadro de gestão visual: tabela de empresas x critérios com rostos coloridos."""
    borda = "1px solid #374151"
    cab = (
        "padding:7px 4px;background:#6B7280;color:#fff;font-size:12px;font-weight:700;"
        f"letter-spacing:.5px;text-align:center;border:{borda};"
    )
    cel = f"border:{borda};height:56px;text-align:center;padding:2px;background:#fff;"
    partes = [
        '<div style="max-width:1000px;margin:4px 0 14px 0;border:6px solid #9CA3AF;border-radius:8px;'
        'background:#fff;font-family:Arial,Helvetica,sans-serif;color:#1F2937;overflow:hidden">',
        '<div style="background:#6B7280;color:#fff;text-align:center;font-weight:800;font-size:20px;'
        'letter-spacing:2px;padding:10px 0">AVALIAÇÃO DE EMPRESAS</div>',
        '<table style="width:100%;border-collapse:collapse;table-layout:fixed">',
        '<colgroup><col style="width:5%"><col style="width:27%">' + '<col style="width:11.33%">' * 6 + "</colgroup>",
        "<tr>" + f'<th style="{cab}">Nº</th><th style="{cab}">EMPRESA</th>'
        + "".join(f'<th style="{cab}">{escape(ROTULO_CRIT[c]).upper()}</th>' for c in COLUNAS_CRIT) + "</tr>",
    ]
    for i in range(total_linhas):
        lin = linhas[i] if i < len(linhas) else None
        partes.append(
            "<tr>"
            f'<td style="{cel}font-weight:700;font-size:13px">{i + 1}</td>'
            f'<td style="{cel}text-align:left;padding-left:10px;font-weight:700;font-size:15px">'
            f'{escape(str(lin["empresa"])) if lin else ""}</td>'
            + "".join(f'<td style="{cel}">{_img(lin[c], 38) if lin and lin[c] in NOTAS else ""}</td>' for c in COLUNAS_CRIT)
            + "</tr>"
        )
    legenda = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:8px;margin-right:26px">{_img(n, 34)}'
        f'<b style="font-size:15px;letter-spacing:.5px">{n.upper()}</b></span>'
        for n in NOTAS
    )
    partes += [
        "</table>",
        '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 16px;'
        'background:#F3F4F6;border-top:1px solid #374151">'
        f"<div>{legenda}</div>"
        f'<div style="font-weight:800;font-size:18px;letter-spacing:1px">{escape(titulo_mes)}</div></div>',
        "</div>",
    ]
    return "".join(partes)