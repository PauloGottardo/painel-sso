"""Acrescenta os botões de relatório em PDF às páginas Termômetro e Acompanhamento.

Execute uma vez, na pasta do projeto:  python aplicar_relatorios.py
Antes de alterar cada página, o script guarda uma cópia com final .bak.
"""
from pathlib import Path

MARCA = "import relatorios"

HELPER_TERMOMETRO = '''def bloco_pdf(tid, chave):
    """Botões para gerar e baixar o relatório em PDF de um preenchimento do Termômetro."""
    linha = termo[termo["id"] == tid].iloc[0]
    st.caption(
        f"Relatório em PDF do preenchimento nº {tid}: {linha['obra']}, "
        f"{linha['data']:%d/%m/%Y}, {linha['pontuacao']} pontos."
    )
    c1, c2, _ = st.columns([1, 1, 2])
    assinatura = relatorios.assinatura_termometro(tid)
    if c1.button("Gerar relatório em PDF", key=f"pdf_gerar_{chave}_{tid}"):
        ss[f"pdf_{chave}"] = (tid, assinatura, relatorios.pdf_termometro(tid))
    pronto = ss.get(f"pdf_{chave}")
    if pronto and pronto[0] == tid and pronto[1] == assinatura:
        c2.download_button(
            "Baixar PDF", data=pronto[2], file_name=relatorios.nome_arquivo_termometro(tid),
            mime="application/pdf", key=f"pdf_baixar_{chave}_{tid}",
        )


'''

BLOCO_ACOMPANHAMENTO = '''with st.expander("Relatório em PDF"):
    todos = banco.listar()
    r1, r2, r3 = st.columns(3)
    obra_rel = r1.selectbox("Obra", ["Todas"] + sorted(todos["obra"].dropna().unique()), key="rel_obra")
    sit_rel = r2.selectbox("Situação", ["Todos", "Em aberto", "Vencidos", "Concluídos"], key="rel_sit")
    periodo_rel = r3.date_input(
        "Período", (todos["data"].min().date(), todos["data"].max().date()),
        format="DD/MM/YYYY", key="rel_periodo",
    )
    if isinstance(periodo_rel, tuple) and len(periodo_rel) == 2:
        ini_rel, fim_rel = pd.Timestamp(periodo_rel[0]), pd.Timestamp(periodo_rel[1])
        rel = todos[(todos["data"] >= ini_rel) & (todos["data"] <= fim_rel)]
        if obra_rel != "Todas":
            rel = rel[rel["obra"] == obra_rel]
        if sit_rel == "Em aberto":
            rel = rel[~rel["fechado"]]
        elif sit_rel == "Vencidos":
            rel = rel[rel["vencido"]]
        elif sit_rel == "Concluídos":
            rel = rel[rel["fechado"]]
        st.caption(f"{len(rel)} desvio(s) no relatório.")
        chave_rel = (obra_rel, sit_rel, ini_rel, fim_rel, len(rel))
        if st.button("Gerar relatório em PDF", key="rel_gerar", disabled=rel.empty):
            st.session_state["rel_pdf"] = (
                chave_rel, relatorios.pdf_desvios(rel, obra_rel, sit_rel, ini_rel, fim_rel),
            )
        pronto = st.session_state.get("rel_pdf")
        if pronto and pronto[0] == chave_rel:
            st.download_button(
                "Baixar PDF", data=pronto[1],
                file_name=relatorios.nome_arquivo_desvios(obra_rel, ini_rel, fim_rel),
                mime="application/pdf", key="rel_baixar",
            )
    else:
        st.info("Escolha a data inicial e a final.")

'''

# (nome, âncora, texto a inserir, inserir depois da âncora?)
PAGINAS = {
    "pages/4_Termometro.py": [
        ("importação", "import banco\n", "import relatorios\n", True),
        ("botões (função)", "def para_data(valor, padrao=None):", HELPER_TERMOMETRO, False),
        ("seção Ações", '    sel = st.selectbox("Preenchimento", ids, format_func=rotulo, key="termo_prenc")\n',
         '    bloco_pdf(sel, "acoes")\n', True),
        ("seção Histórico", '    with st.expander("Excluir este preenchimento"):', '    bloco_pdf(tid, "hist")\n\n', False),
    ],
    "pages/3_Acompanhamento.py": [
        ("importação", "import banco\n", "import relatorios\n", True),
        ("bloco do relatório", 'STATUS = ["Aberto", "Concluído"]', BLOCO_ACOMPANHAMENTO, False),
    ],
}


def aplicar(arquivo, passos):
    p = Path(arquivo)
    if not p.exists():
        print(f"[ERRO] {arquivo} não encontrado. Rode o script dentro da pasta do projeto (C:\\painel_sso).")
        return
    texto = p.read_text(encoding="utf-8")
    if MARCA in texto:
        print(f"[OK] {arquivo} já estava atualizado.")
        return
    novo = texto
    for nome, ancora, inserir, depois in passos:
        if novo.count(ancora) != 1:
            print(f"[ERRO] {arquivo}: não encontrei o ponto '{nome}'. Este arquivo NÃO foi alterado.")
            return
        novo = novo.replace(ancora, ancora + inserir if depois else inserir + ancora, 1)
    Path(str(p) + ".bak").write_text(texto, encoding="utf-8")
    p.write_text(novo, encoding="utf-8")
    print(f"[OK] {arquivo} atualizado (cópia de segurança: {p.name}.bak).")


for arquivo, passos in PAGINAS.items():
    aplicar(arquivo, passos)