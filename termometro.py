"""Termômetro de Segurança da Obra: perguntas, cálculos e acesso ao banco."""
import io
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

import pandas as pd
from PIL import Image, ImageOps

import banco

# (número, grupo, pergunta, pontos)
PERGUNTAS = [
    (1, "Equipe", "Há pessoas novas no time?", 2),
    (2, "Equipe", "Faltou alguém do time?", 1),
    (3, "Equipe", "Alguém do time pode estar com alguma dúvida em relação às atividades a serem executadas?", 2),
    (4, "Local e ambiente", "O local está desorganizado (entulho, materiais soltos)?", 2),
    (5, "Local e ambiente", "Há risco de queda de materiais de níveis superiores?", 3),
    (6, "Local e ambiente", "Os acessos (escadas, rampas) estão instáveis?", 3),
    (7, "Local e ambiente", "O clima (chuva, vento forte, calor extremo) pode atrapalhar?", 1),
    (8, "Equipamentos e materiais", "As ferramentas apresentam algum tipo de defeito?", 3),
    (9, "Equipamentos e materiais", "Os EPIs não estão em condições de uso?", 3),
    (10, "Equipamentos e materiais", "Há máquinas ou veículos circulando perto da área?", 2),
    (11, "Equipamentos e materiais", "Os materiais estão mal armazenados ou instáveis (risco de tombar)?", 2),
    (12, "Atividades de risco", "Haverá escavação abaixo de 1,25 m?", 3),
    (13, "Atividades de risco", "Haverá trabalho em altura acima de 2 m?", 3),
    (14, "Atividades de risco", "Haverá atividades simultâneas com riscos entre si?", 3),
    (15, "Atividades de risco", "Há risco elétrico próximo (fios expostos, quadros abertos)?", 3),
    (16, "Atividades de risco", "Haverá movimentação de cargas suspensas (içamento)?", 3),
    (17, "Atividades de risco", "Haverá uso de ferramentas elétricas ou rotativas?", 2),
]
PERG = {n: (grupo, texto, pts) for n, grupo, texto, pts in PERGUNTAS}
GRUPOS = list(dict.fromkeys(g for _, g, _, _ in PERGUNTAS))
PONTOS_MAX = sum(p for _, _, _, p in PERGUNTAS)

# Faixas da ferramenta: 0-15 baixo, 16-30 médio, 31 ou mais alto
SIGNIFICADO = {
    "Baixo": "Condições aceitáveis; seguir com atenção.",
    "Médio": "Ajustar condições antes de iniciar; atenção redobrada.",
    "Alto": "Parar, revisar planejamento e eliminar riscos antes de começar.",
}
CORES = {"Baixo": "#2E7D32", "Médio": "#F9A825", "Alto": "#C62828"}


def faixa(pontos: float) -> str:
    if pontos <= 15:
        return "Baixo"
    if pontos <= 30:
        return "Médio"
    return "Alto"


def calcular(respostas: dict) -> int:
    """Soma os pontos das perguntas respondidas com SIM."""
    return sum(pts for n, _, _, pts in PERGUNTAS if respostas.get(n))


def curto(numero: int, limite: int = 48) -> str:
    texto = PERG[numero][1]
    if len(texto) > limite:
        texto = texto[: limite - 1].rstrip() + "…"
    return f"{numero}. {texto}"


def inicio_periodo(datas: pd.Series, base: str) -> pd.Series:
    """Primeiro dia do período (dia, semana iniciada na segunda, ou mês)."""
    if base == "Semana":
        return datas.dt.to_period("W").dt.start_time
    if base == "Mês":
        return datas.dt.to_period("M").dt.start_time
    return datas.dt.normalize()


def rotulo_periodo(inicio: pd.Timestamp, base: str) -> str:
    if base == "Semana":
        return "Sem. " + inicio.strftime("%d/%m")
    if base == "Mês":
        return inicio.strftime("%m/%Y")
    return inicio.strftime("%d/%m/%y")


# ---------------- fotos ----------------
PASTA_FOTOS = Path("dados/fotos")
TIPOS_FOTO = ["jpg", "jpeg", "png"]
MOMENTOS = {"antes": "Antes (não conformidade)", "depois": "Depois (resolvida)"}


# ---------------- banco de dados ----------------
def conectar():
    con = banco.conectar()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS termometro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            obra TEXT NOT NULL,
            empresa TEXT,
            responsavel TEXT,
            pontuacao INTEGER NOT NULL,
            observacao TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS termometro_respostas (
            termometro_id INTEGER NOT NULL,
            pergunta INTEGER NOT NULL,
            sim INTEGER NOT NULL,
            PRIMARY KEY (termometro_id, pergunta)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS termometro_acoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termometro_id INTEGER NOT NULL,
            pergunta INTEGER NOT NULL,
            acao TEXT NOT NULL,
            responsavel TEXT,
            prazo TEXT,
            status TEXT DEFAULT 'Aberta',
            data_fechamento TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS termometro_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acao_id INTEGER NOT NULL,
            momento TEXT NOT NULL,
            arquivo TEXT NOT NULL
        )
        """
    )
    con.commit()
    return con


def salvar(data, obra, empresa, responsavel, respostas, observacao) -> int:
    pontos = calcular(respostas)
    with closing(conectar()) as con:
        cur = con.execute(
            "INSERT INTO termometro (data, obra, empresa, responsavel, pontuacao, observacao) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (banco._iso(data), obra, empresa, responsavel, pontos, observacao),
        )
        novo_id = cur.lastrowid
        con.executemany(
            "INSERT INTO termometro_respostas (termometro_id, pergunta, sim) VALUES (?, ?, ?)",
            [(novo_id, n, int(bool(respostas.get(n)))) for n, _, _, _ in PERGUNTAS],
        )
        con.commit()
    return novo_id


def listar() -> pd.DataFrame:
    with closing(conectar()) as con:
        df = pd.read_sql_query("SELECT * FROM termometro", con)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["faixa"] = df["pontuacao"].map(faixa)
    return df


def respostas_detalhadas() -> pd.DataFrame:
    with closing(conectar()) as con:
        df = pd.read_sql_query(
            """
            SELECT r.termometro_id, r.pergunta, r.sim, t.data, t.obra, t.empresa
            FROM termometro_respostas r
            JOIN termometro t ON t.id = r.termometro_id
            """,
            con,
        )
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    return df


def respostas_sim(termometro_id: int) -> list:
    with closing(conectar()) as con:
        linhas = con.execute(
            "SELECT pergunta FROM termometro_respostas "
            "WHERE termometro_id = ? AND sim = 1 ORDER BY pergunta",
            (termometro_id,),
        ).fetchall()
    return [l[0] for l in linhas]


def excluir(termometro_id: int) -> None:
    with closing(conectar()) as con:
        ids = [l[0] for l in con.execute(
            "SELECT id FROM termometro_acoes WHERE termometro_id = ?", (termometro_id,)
        ).fetchall()]
        _apagar_fotos(con, ids)
        con.execute("DELETE FROM termometro_acoes WHERE termometro_id = ?", (termometro_id,))
        con.execute("DELETE FROM termometro_respostas WHERE termometro_id = ?", (termometro_id,))
        con.execute("DELETE FROM termometro WHERE id = ?", (termometro_id,))
        con.commit()


# ---------------- ações ----------------
def criar_acao(termometro_id, pergunta, acao, responsavel, prazo) -> int:
    with closing(conectar()) as con:
        cur = con.execute(
            "INSERT INTO termometro_acoes (termometro_id, pergunta, acao, responsavel, prazo, status) "
            "VALUES (?, ?, ?, ?, ?, 'Aberta')",
            (termometro_id, pergunta, acao, responsavel, banco._iso(prazo)),
        )
        con.commit()
        return cur.lastrowid


def listar_acoes() -> pd.DataFrame:
    with closing(conectar()) as con:
        df = pd.read_sql_query(
            """
            SELECT a.*, t.data AS data_preenchimento, t.obra, t.empresa,
                (SELECT COUNT(*) FROM termometro_fotos f
                  WHERE f.acao_id = a.id AND f.momento = 'antes') AS fotos_antes,
                (SELECT COUNT(*) FROM termometro_fotos f
                  WHERE f.acao_id = a.id AND f.momento = 'depois') AS fotos_depois
            FROM termometro_acoes a
            JOIN termometro t ON t.id = a.termometro_id
            """,
            con,
        )
    for col in ["prazo", "data_fechamento", "data_preenchimento"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["status"] = df["status"].fillna("Aberta").astype(str).str.strip()
    df["fechada"] = df["status"].str.lower().str.startswith("conclu")
    hoje = pd.Timestamp.today().normalize()
    df["vencida"] = (~df["fechada"]) & (df["prazo"] < hoje)
    df["situacao"] = df["status"]
    df.loc[df["vencida"], "situacao"] = "Vencida"
    df["desvio"] = df["pergunta"].map(lambda n: curto(int(n), 60))
    df["fotos"] = df["fotos_antes"].astype(str) + " / " + df["fotos_depois"].astype(str)
    return df


def obter_acao(acao_id: int) -> dict:
    with closing(conectar()) as con:
        con.row_factory = sqlite3.Row
        linha = con.execute(
            "SELECT * FROM termometro_acoes WHERE id = ?", (acao_id,)
        ).fetchone()
    return dict(linha) if linha else {}


def atualizar_acao(acao_id, acao, responsavel, prazo, status, data_fechamento) -> None:
    with closing(conectar()) as con:
        con.execute(
            "UPDATE termometro_acoes SET acao = ?, responsavel = ?, prazo = ?, "
            "status = ?, data_fechamento = ? WHERE id = ?",
            (acao, responsavel, banco._iso(prazo), status, banco._iso(data_fechamento), acao_id),
        )
        con.commit()


def excluir_acao(acao_id: int) -> None:
    with closing(conectar()) as con:
        _apagar_fotos(con, [acao_id])
        con.execute("DELETE FROM termometro_acoes WHERE id = ?", (acao_id,))
        con.commit()


# ---------------- fotos das ações ----------------
def _preparar_imagem(conteudo: bytes) -> bytes:
    """Corrige a rotação, reduz para no máximo 1600 px e salva como JPEG."""
    img = Image.open(io.BytesIO(conteudo))
    img = ImageOps.exif_transpose(img)
    img.thumbnail((1600, 1600))
    if img.mode != "RGB":
        img = img.convert("RGB")
    saida = io.BytesIO()
    img.save(saida, format="JPEG", quality=85, optimize=True)
    return saida.getvalue()


def salvar_fotos(acao_id: int, momento: str, arquivos) -> int:
    """Salva as fotos enviadas (uploads do Streamlit). Retorna quantas foram salvas."""
    if momento not in MOMENTOS:
        raise ValueError("momento deve ser 'antes' ou 'depois'")
    PASTA_FOTOS.mkdir(parents=True, exist_ok=True)
    salvas = 0
    with closing(conectar()) as con:
        for arq in arquivos or []:
            try:
                dados = _preparar_imagem(arq.getvalue())
            except Exception:
                continue  # arquivo que não é uma imagem válida
            nome = f"acao{acao_id}_{momento}_{uuid.uuid4().hex[:8]}.jpg"
            (PASTA_FOTOS / nome).write_bytes(dados)
            con.execute(
                "INSERT INTO termometro_fotos (acao_id, momento, arquivo) VALUES (?, ?, ?)",
                (acao_id, momento, nome),
            )
            salvas += 1
        con.commit()
    return salvas


def listar_fotos(acao_id: int) -> list:
    with closing(conectar()) as con:
        linhas = con.execute(
            "SELECT id, momento, arquivo FROM termometro_fotos WHERE acao_id = ? ORDER BY id",
            (acao_id,),
        ).fetchall()
    return [
        {"id": i, "momento": m, "arquivo": a, "caminho": PASTA_FOTOS / a}
        for i, m, a in linhas
    ]


def remover_foto(foto_id: int) -> None:
    with closing(conectar()) as con:
        linha = con.execute(
            "SELECT arquivo FROM termometro_fotos WHERE id = ?", (foto_id,)
        ).fetchone()
        if linha:
            (PASTA_FOTOS / linha[0]).unlink(missing_ok=True)
        con.execute("DELETE FROM termometro_fotos WHERE id = ?", (foto_id,))
        con.commit()


def _apagar_fotos(con, ids_acoes: list) -> None:
    """Apaga os arquivos e os registros de fotos das ações indicadas."""
    for acao_id in ids_acoes:
        for (arquivo,) in con.execute(
            "SELECT arquivo FROM termometro_fotos WHERE acao_id = ?", (acao_id,)
        ).fetchall():
            (PASTA_FOTOS / arquivo).unlink(missing_ok=True)
        con.execute("DELETE FROM termometro_fotos WHERE acao_id = ?", (acao_id,))

# ---------------- gráficos de ações ----------------
def preparar_acoes(acoes: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta colunas de apoio para os gráficos e indicadores de ações."""
    a = acoes.copy()
    hoje = pd.Timestamp.today().normalize()
    a["situacao_g"] = a["situacao"].replace({"Aberta": "Em aberto"})
    a["no_prazo"] = (
        a["fechada"] & a["data_fechamento"].notna() & (a["data_fechamento"] <= a["prazo"])
    )
    a["dias_conclusao"] = (a["data_fechamento"] - a["data_preenchimento"]).dt.days.where(a["fechada"])
    a["dias_atraso"] = (hoje - a["prazo"]).dt.days.where(a["vencida"])
    return a


def acoes_por_periodo(a: pd.DataFrame, base: str) -> pd.DataFrame:
    """Quantidade de ações por período de abertura e por situação."""
    t = a.assign(periodo=inicio_periodo(a["data_preenchimento"], base))
    r = (
        t.groupby(["periodo", "situacao_g"])
        .size()
        .reset_index(name="quantidade")
        .sort_values("periodo")
    )
    r["rotulo"] = r["periodo"].map(lambda p: rotulo_periodo(p, base))
    return r


def fluxo_acoes(a: pd.DataFrame, base: str) -> pd.DataFrame:
    """Ações abertas (pela data do preenchimento) e concluídas (pela data de conclusão) por período."""
    abertas = (
        a.assign(periodo=inicio_periodo(a["data_preenchimento"], base))
        .groupby("periodo").size().rename("Abertas")
    )
    c = a[a["fechada"] & a["data_fechamento"].notna()]
    concluidas = (
        c.assign(periodo=inicio_periodo(c["data_fechamento"], base))
        .groupby("periodo").size().rename("Concluídas")
    )
    f = (
        pd.concat([abertas, concluidas], axis=1)
        .fillna(0).astype(int).reset_index().sort_values("periodo")
    )
    f = f.melt(id_vars="periodo", var_name="tipo", value_name="quantidade")
    f["rotulo"] = f["periodo"].map(lambda p: rotulo_periodo(p, base))
    return f