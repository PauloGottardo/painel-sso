"""Funções de banco de dados (SQLite) e listas de opções do painel de SSO."""
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

import pandas as pd

DB = Path("dados/sso.db")
LOGO = Path("logo.png")

# ---- Opções iniciais das listas (depois, gerencie na página Configurações) ----
PADRAO_OPCOES = {
    "obra": ["Obra A", "Obra B"],
    "local": ["Almoxarifado", "Fachada", "Laje 3", "Escada", "Central de carpintaria",
              "Acesso principal", "Subsolo", "Área de vivência"],
    "tipo": ["Condição insegura", "Comportamento inseguro"],
    "categoria": ["EPI", "Trabalho em altura", "Organização e limpeza",
                  "Instalações elétricas", "Escavação", "Máquinas e equipamentos"],
    "empreiteira": ["Empreiteira 1", "Empreiteira 2", "Empreiteira 3"],
}
GRAVIDADES = ["Baixa", "Média", "Alta"]

COLUNAS = [
    "data", "obra", "local", "tipo", "categoria", "empreiteira", "gravidade",
    "descricao", "acao_corretiva", "responsavel", "prazo", "status",
    "data_fechamento",
]


def conectar():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS desvios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            obra TEXT,
            local TEXT,
            tipo TEXT,
            categoria TEXT,
            empreiteira TEXT,
            gravidade TEXT,
            descricao TEXT,
            acao_corretiva TEXT,
            responsavel TEXT,
            prazo TEXT,
            status TEXT DEFAULT 'Aberto',
            data_fechamento TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS opcoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lista TEXT NOT NULL,
            valor TEXT NOT NULL,
            UNIQUE (lista, valor)
        )
        """
    )
    if con.execute("SELECT COUNT(*) FROM opcoes").fetchone()[0] == 0:
        for lista, valores in PADRAO_OPCOES.items():
            con.executemany(
                "INSERT INTO opcoes (lista, valor) VALUES (?, ?)",
                [(lista, v) for v in valores],
            )
    con.commit()
    return con


def _iso(valor):
    """Converte data/Timestamp para texto AAAA-MM-DD (ou None)."""
    if valor is None or pd.isna(valor):
        return None
    return pd.Timestamp(valor).date().isoformat()


def inserir(registro: dict) -> None:
    dados = {c: registro.get(c) for c in COLUNAS}
    for c in ("data", "prazo", "data_fechamento"):
        dados[c] = _iso(dados[c])
    dados["status"] = dados["status"] or "Aberto"
    colunas = ", ".join(COLUNAS)
    marcas = ", ".join("?" for _ in COLUNAS)
    with closing(conectar()) as con:
        con.execute(
            f"INSERT INTO desvios ({colunas}) VALUES ({marcas})",
            [dados[c] for c in COLUNAS],
        )
        con.commit()


def contar() -> int:
    with closing(conectar()) as con:
        return con.execute("SELECT COUNT(*) FROM desvios").fetchone()[0]


def listar() -> pd.DataFrame:
    """Retorna todos os desvios, já com as colunas calculadas."""
    with closing(conectar()) as con:
        df = pd.read_sql_query("SELECT * FROM desvios", con)

    for col in ["data", "prazo", "data_fechamento"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["status"] = df["status"].fillna("Aberto").astype(str).str.strip()
    df["fechado"] = df["status"].str.lower().isin(["concluído", "concluido"])

    hoje = pd.Timestamp.today().normalize()
    df["vencido"] = (~df["fechado"]) & (df["prazo"] < hoje)
    df["dias_para_fechar"] = (df["data_fechamento"] - df["data"]).dt.days
    return df


def _chave(texto: str) -> str:
    """Texto sem acentos e em minúsculas, para ordenar e comparar."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


def opcoes(lista: str) -> list:
    """Opções cadastradas de uma lista (obra, local, tipo, categoria, empreiteira)."""
    with closing(conectar()) as con:
        linhas = con.execute(
            "SELECT valor FROM opcoes WHERE lista = ?", (lista,)
        ).fetchall()
    return sorted((l[0] for l in linhas), key=_chave)


def adicionar_opcao(lista: str, valor: str) -> str:
    """Adiciona uma opção. Retorna 'ok', 'vazio', 'longo' ou 'duplicado'."""
    valor = " ".join(valor.split())
    if not valor:
        return "vazio"
    if len(valor) > 60:
        return "longo"
    if _chave(valor) in {_chave(v) for v in opcoes(lista)}:
        return "duplicado"
    with closing(conectar()) as con:
        con.execute("INSERT INTO opcoes (lista, valor) VALUES (?, ?)", (lista, valor))
        con.commit()
    return "ok"


def remover_opcoes(lista: str, valores: list) -> None:
    with closing(conectar()) as con:
        con.executemany(
            "DELETE FROM opcoes WHERE lista = ? AND valor = ?",
            [(lista, v) for v in valores],
        )
        con.commit()


def logo_lateral() -> None:
    """Mostra o logo da empresa no topo da barra lateral."""
    import streamlit as st

    if LOGO.exists():
        st.sidebar.image(str(LOGO), width=200)