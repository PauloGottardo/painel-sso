\# Painel de Desvios e Inspeções de SSO



Protótipo de painel para gestão de inspeções de segurança do trabalho em obras, feito em Python com Streamlit.



> Projeto em fase de desenvolvimento e testes. Os dados de exemplo são fictícios.



\## O que faz

\- Cadastro de desvios (condição ou comportamento inseguro) direto no sistema

\- Painel com indicadores: desvios por tipo, categoria, empreiteira e local, tempo de fechamento e pendências vencidas

\- Página de configurações para gerenciar obras, locais, tipos, categorias e empreiteiras

\- Acompanhamento das ações: concluir, editar e excluir desvios



\## Como executar

```bash

conda create -n sso python=3.11 -y

conda activate sso

pip install -r requirements.txt

python gerar\_modelo.py

python importar\_planilha.py

streamlit run app.py

```



Os comandos `gerar\_modelo.py` e `importar\_planilha.py` criam dados fictícios para teste. Os dados ficam em `dados/sso.db` (SQLite), que não é versionado.



Para exibir um logo no painel, coloque um arquivo `logo.png` na pasta do projeto.



\## Próximos passos

\- Anexar imagens aos desvios

\- Relatórios em PDF


