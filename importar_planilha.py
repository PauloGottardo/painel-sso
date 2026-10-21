"""Importa dados/inspecoes.xlsx (dados de exemplo) para o banco de dados.

Só importa se o banco estiver vazio, para não duplicar registros.
"""
import pandas as pd

import banco

if banco.contar() > 0:
    print("O banco já tem registros. Nada foi importado.")
    raise SystemExit

df = pd.read_excel("dados/inspecoes.xlsx")
df.columns = [str(c).strip().lower() for c in df.columns]

for _, linha in df.iterrows():
    registro = {c: (None if pd.isna(linha.get(c)) else linha.get(c)) for c in banco.COLUNAS}
    banco.inserir(registro)

print(f"{len(df)} registros importados para o banco.")