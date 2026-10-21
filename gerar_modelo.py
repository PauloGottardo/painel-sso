import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

obras = ["Obra A", "Obra B"]
locais = ["Almoxarifado", "Fachada", "Laje 3", "Escada", "Central de carpintaria",
          "Acesso principal", "Subsolo", "Área de vivência"]
tipos = ["Condição insegura", "Comportamento inseguro"]
categorias = ["EPI", "Trabalho em altura", "Organização e limpeza",
              "Instalações elétricas", "Escavação", "Máquinas e equipamentos"]
empreiteiras = ["Empreiteira 1", "Empreiteira 2", "Empreiteira 3"]
gravidades = ["Baixa", "Média", "Alta"]

linhas = []
inicio = date.today() - timedelta(days=60)
for i in range(60):
    data = inicio + timedelta(days=random.randint(0, 59))
    prazo = data + timedelta(days=random.choice([1, 3, 7]))
    concluido = random.random() < 0.7
    fechamento = (
        data + timedelta(days=random.randint(0, 10)) if concluido else None
    )
    linhas.append({
        "data": data,
        "obra": random.choice(obras),
        "local": random.choice(locais),
        "tipo": random.choice(tipos),
        "categoria": random.choice(categorias),
        "empreiteira": random.choice(empreiteiras),
        "gravidade": random.choice(gravidades),
        "descricao": "Descrição do desvio (exemplo)",
        "acao_corretiva": "Ação corretiva (exemplo)",
        "responsavel": "Encarregado (exemplo)",
        "prazo": prazo,
        "status": "Concluído" if concluido else "Aberto",
        "data_fechamento": fechamento,
    })

Path("dados").mkdir(exist_ok=True)
pd.DataFrame(linhas).to_excel("dados/inspecoes.xlsx", index=False)
print("Planilha de exemplo criada em dados/inspecoes.xlsx")