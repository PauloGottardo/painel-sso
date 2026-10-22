"""Termômetro de Segurança da Obra: perguntas, cálculos e acesso ao banco."""
from contextlib import closing

import pandas as pd

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
        con.execute("DELETE FROM termometro_acoes WHERE termometro_id = ?", (termometro_id,))
        con.execute("DELETE FROM termometro_respostas WHERE termometro_id = ?", (termometro_id,))
        con.execute("DELETE FROM termometro WHERE id = ?", (termometro_id,))
        con.commit()


# ---------------- ações ----------------
def criar_acao(termometro_id, pergunta, acao, responsavel, prazo) -> None:
    with closing(conectar()) as con:
        con.execute(
            "INSERT INTO termometro_acoes (termometro_id, pergunta, acao, responsavel, prazo, status) "
            "VALUES (?, ?, ?, ?, ?, 'Aberta')",
            (termometro_id, pergunta, acao, responsavel, banco._iso(prazo)),
        )
        con.commit()


def listar_acoes() -> pd.DataFrame:
    with closing(conectar()) as con:
        df = pd.read_sql_query(
            """
            SELECT a.*, t.data AS data_preenchimento, t.obra, t.empresa
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
    return df


def obter_acao(acao_id: int) -> dict:
    with closing(conectar()) as con:
        import sqlite3

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
        con.execute("DELETE FROM termometro_acoes WHERE id = ?", (acao_id,))
        con.commit()