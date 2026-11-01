"""Relatórios em PDF do SegObra: Termômetro de Segurança da Obra e desvios de inspeção."""
import io
import re
import unicodedata
from datetime import datetime
from xml.sax.saxutils import escape

import pandas as pd
from PIL import Image as PILImage
from reportlab.graphics.shapes import Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

import banco
import termometro as tm

MARGEM = 15 * mm
VERDE = colors.HexColor("#2E7D32")
VERDE_ESC = colors.HexColor("#14532D")
VERDE_CL = colors.HexColor("#E8F2E9")
CINZA = colors.HexColor("#6B7280")
CINZA_CL = colors.HexColor("#F3F4F6")
LINHA = colors.HexColor("#D1D5DB")
TEXTO = colors.HexColor("#1F2937")
AMBAR = colors.HexColor("#F9A825")
VERMELHO = colors.HexColor("#C62828")
VERMELHO_CL = colors.HexColor("#FDECEA")
AZUL = colors.HexColor("#1E88E5")

COR_FAIXA = {"Baixo": VERDE, "Médio": AMBAR, "Alto": VERMELHO}
HEX_SITUACAO = {
    "Concluída": "#2E7D32", "Concluído": "#2E7D32", "Vencida": "#C62828", "Vencido": "#C62828",
    "Aberta": "#1E88E5", "Em aberto": "#1E88E5",
}


def _estilo(nome, **kw):
    base = dict(fontName="Helvetica", fontSize=9, leading=12, textColor=TEXTO)
    base.update(kw)
    return ParagraphStyle(nome, **base)


E_NORMAL = _estilo("normal")
E_PEQ = _estilo("peq", fontSize=8, leading=10)
E_CEL = _estilo("cel", fontSize=8.5, leading=11)
E_CEL_PEQ = _estilo("celpeq", fontSize=7.5, leading=9.5)
E_ROT = _estilo("rot", fontSize=8, leading=10, textColor=CINZA, fontName="Helvetica-Bold")
E_H2 = _estilo("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=VERDE_ESC)
E_CENTRO = _estilo("centro", alignment=TA_CENTER)
E_DIREITA = _estilo("direita", alignment=TA_RIGHT)
E_NOTA = _estilo("nota", fontSize=8, leading=10, textColor=CINZA, fontName="Helvetica-Oblique")


# ---------------------------------------------------------------- utilidades
def _p(texto, estilo=E_CEL):
    """Parágrafo com o texto escapado e quebras de linha preservadas."""
    texto = "" if texto is None or (not isinstance(texto, str) and pd.isna(texto)) else str(texto)
    return Paragraph(escape(texto).replace("\n", "<br/>"), estilo)


def _data(v):
    if v is None or pd.isna(v):
        return "-"
    return pd.Timestamp(v).strftime("%d/%m/%Y")


def _slug(texto):
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "relatorio"


def _secao(texto, largura):
    t = Table([[Paragraph(escape(texto), E_H2)]], colWidths=[largura])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1, VERDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _kpis(itens, largura):
    """Faixa de indicadores. itens: lista de (valor, rótulo, cor hex)."""
    n = len(itens)
    cel = largura / n
    valores = [
        Paragraph(f'<font color="{cor}" size="19"><b>{escape(str(v))}</b></font>', _estilo("kv", leading=23, alignment=TA_CENTER))
        for v, _, cor in itens
    ]
    rotulos = [Paragraph(escape(r), _estilo("kr", fontSize=8, leading=10, textColor=CINZA, alignment=TA_CENTER)) for _, r, _ in itens]
    t = Table([valores, rotulos], colWidths=[cel] * n)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_CL),
        ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
        ("BOX", (0, 0), (-1, -1), 3, colors.white),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _imagem(caminho, w_max, h_max):
    """Imagem reduzida (para o PDF não ficar pesado) e ajustada à caixa w_max x h_max."""
    img = PILImage.open(caminho).convert("RGB")
    img.thumbnail((900, 900))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    buf.seek(0)
    iw, ih = img.size
    r = min(w_max / iw, h_max / ih)
    return Image(buf, width=iw * r, height=ih * r)


def _grade_fotos(fotos, largura, por_linha=2):
    if not fotos:
        return Paragraph("Sem fotos registradas.", E_NOTA)
    cel = largura / por_linha
    linhas, linha = [], []
    for f in fotos:
        try:
            linha.append(_imagem(f["caminho"], cel - 4 * mm, 52 * mm))
        except Exception:
            linha.append(Paragraph("(foto indisponível)", E_NOTA))
        if len(linha) == por_linha:
            linhas.append(linha)
            linha = []
    if linha:
        linhas.append(linha + [""] * (por_linha - len(linha)))
    t = Table(linhas, colWidths=[cel] * por_linha)
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# ---------------------------------------------------------------- documento
def _cabecalho(titulo, subtitulo, pagesize):
    def desenhar(c, doc):
        w, h = pagesize
        c.saveState()
        x = MARGEM
        if banco.LOGO.exists():
            try:
                leitor = ImageReader(str(banco.LOGO))
                iw, ih = leitor.getSize()
                alt = 16 * mm
                larg = alt * iw / ih
                c.drawImage(leitor, x, h - 8 * mm - alt, width=larg, height=alt, mask="auto")
                x += larg + 6 * mm
            except Exception:
                pass
        c.setFillColor(VERDE_ESC)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(x, h - 16 * mm, titulo)
        c.setFillColor(CINZA)
        c.setFont("Helvetica", 9)
        c.drawString(x, h - 21.5 * mm, subtitulo)
        c.setStrokeColor(VERDE)
        c.setLineWidth(1.5)
        c.line(MARGEM, h - 26.5 * mm, w - MARGEM, h - 26.5 * mm)
        c.restoreState()
    return desenhar


def _canvas_numerado(pagesize):
    gerado = datetime.now().strftime("%d/%m/%Y às %H:%M")

    class _Canvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._estados = []

        def showPage(self):
            self._estados.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._estados)
            for estado in self._estados:
                self.__dict__.update(estado)
                self._rodape(total)
                super().showPage()
            super().save()

        def _rodape(self, total):
            w, _ = pagesize
            self.saveState()
            self.setStrokeColor(LINHA)
            self.setLineWidth(0.5)
            self.line(MARGEM, 14 * mm, w - MARGEM, 14 * mm)
            self.setFont("Helvetica", 8)
            self.setFillColor(CINZA)
            self.drawString(MARGEM, 9.5 * mm, "SegObra · Painel de gestão de segurança do trabalho")
            self.drawCentredString(w / 2, 9.5 * mm, f"Gerado em {gerado}")
            self.drawRightString(w - MARGEM, 9.5 * mm, f"Página {self._pageNumber} de {total}")
            self.restoreState()

    return _Canvas


def _montar(story, pagesize, titulo, subtitulo) -> bytes:
    buf = io.BytesIO()
    w, h = pagesize
    doc = BaseDocTemplate(
        buf, pagesize=pagesize, leftMargin=MARGEM, rightMargin=MARGEM, topMargin=31 * mm,
        bottomMargin=19 * mm, title=titulo, author="SegObra",
    )
    quadro = Frame(MARGEM, 19 * mm, w - 2 * MARGEM, h - 19 * mm - 31 * mm, id="quadro",
                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="pagina", frames=[quadro], onPage=_cabecalho(titulo, subtitulo, pagesize))])
    doc.build(story, canvasmaker=_canvas_numerado(pagesize))
    return buf.getvalue()


# ======================================================================
# TERMÔMETRO DE SEGURANÇA DA OBRA
# ======================================================================
def _grafico_faixas(pontos, largura):
    """Barra com as três faixas de risco e um marcador na pontuação obtida."""
    pad = 9 * mm
    d = Drawing(largura, 33 * mm)
    y0, alt = 8 * mm, 9 * mm
    escala = (largura - 2 * pad) / tm.PONTOS_MAX
    segmentos = [
        (0, 15, VERDE, "Baixo  0 a 15", colors.white),
        (15, 30, AMBAR, "Médio  16 a 30", TEXTO),
        (30, tm.PONTOS_MAX, VERMELHO, "Alto  31 ou mais", colors.white),
    ]
    for ini, fim, cor, rot, cor_txt in segmentos:
        d.add(Rect(pad + ini * escala, y0, (fim - ini) * escala, alt, fillColor=cor, strokeColor=colors.white, strokeWidth=1))
        d.add(String(pad + (ini + fim) / 2 * escala, y0 + 2.8 * mm, rot, textAnchor="middle",
                     fontName="Helvetica-Bold", fontSize=8, fillColor=cor_txt))
    x = pad + pontos * escala
    d.add(Polygon([x - 3 * mm, y0 + alt + 7 * mm, x + 3 * mm, y0 + alt + 7 * mm, x, y0 + alt + 1 * mm],
                  fillColor=TEXTO, strokeColor=None))
    d.add(String(x, y0 + alt + 9 * mm, f"{pontos} pts", textAnchor="middle",
                 fontName="Helvetica-Bold", fontSize=10, fillColor=TEXTO))
    for v in (0, 15, 30, tm.PONTOS_MAX):
        d.add(String(pad + v * escala, 2 * mm, str(v), textAnchor="middle", fontName="Helvetica", fontSize=7.5, fillColor=CINZA))
    return d


def _cartao_acao(a, fotos, largura):
    """Cartão de uma ação: dados, situação e fotos do antes e do depois."""
    hex_sit = HEX_SITUACAO.get(a["situacao"], "#1F2937")
    cab = Paragraph(f"<b>Ação nº {int(a['id'])}</b>", _estilo("ca", fontSize=9.5, textColor=VERDE_ESC))
    sit = Paragraph(f'<font color="{hex_sit}"><b>{escape(str(a["situacao"]).upper())}</b></font>',
                    _estilo("cs", fontSize=8.5, alignment=TA_RIGHT))
    c1, c2 = 30 * mm, (largura - 60 * mm) / 2
    dados = [
        [cab, "", "", sit],
        [Paragraph("Ação", E_ROT), _p(a["acao"]), "", ""],
        [Paragraph("Responsável", E_ROT), _p(a["responsavel"] or "-"), Paragraph("Prazo", E_ROT), _p(_data(a["prazo"]))],
        [Paragraph("Preenchimento", E_ROT), _p(_data(a["data_preenchimento"])), Paragraph("Concluída em", E_ROT), _p(_data(a["data_fechamento"]))],
    ]
    t = Table(dados, colWidths=[c1, c2, 30 * mm, c2])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (2, 0)),
        ("SPAN", (1, 1), (3, 1)),
        ("BACKGROUND", (0, 0), (-1, 0), VERDE_CL),
        ("BOX", (0, 0), (-1, -1), 0.6, LINHA),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    antes = [f for f in fotos if f["momento"] == "antes"]
    depois = [f for f in fotos if f["momento"] == "depois"]
    meio = largura / 2
    ft = Table(
        [
            [Paragraph(f"<b>Antes</b> ({len(antes)})", E_CEL), Paragraph(f"<b>Depois</b> ({len(depois)})", E_CEL)],
            [_grade_fotos(antes, meio - 6 * mm), _grade_fotos(depois, meio - 6 * mm)],
        ],
        colWidths=[meio, meio],
    )
    ft.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CINZA_CL),
        ("BOX", (0, 0), (-1, -1), 0.6, LINHA),
        ("LINEAFTER", (0, 0), (0, -1), 0.6, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 3),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
    ]))
    return [t, ft, Spacer(1, 5 * mm)]


def _assinaturas(largura):
    meio = largura / 2
    linhas = [
        ["", ""],
        [Paragraph("Técnico de Segurança do Trabalho", E_PEQ), Paragraph("Responsável pela obra ou empresa", E_PEQ)],
    ]
    t = Table(linhas, colWidths=[meio, meio], rowHeights=[14 * mm, None])
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), 0.6, TEXTO),
        ("LINEABOVE", (1, 1), (1, 1), 0.6, TEXTO),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 18 * mm),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
    ]))
    return t


def pdf_termometro(tid: int) -> bytes:
    """Relatório de um preenchimento do Termômetro (data e obra em que foi registrado)."""
    termo = tm.listar()
    achou = termo[termo["id"] == tid]
    if achou.empty:
        raise ValueError("Preenchimento não encontrado.")
    t = achou.iloc[0]
    pontos = int(t["pontuacao"])
    fx = tm.faixa(pontos)
    sim = set(tm.respostas_sim(tid))
    acoes = tm.listar_acoes()
    acoes = acoes[acoes["termometro_id"] == tid].sort_values("id")
    largura = A4[0] - 2 * MARGEM
    story = []

    # ---- dados do preenchimento
    story.append(_secao("Dados do preenchimento", largura))
    story.append(Spacer(1, 2 * mm))
    info = [
        [Paragraph("Obra", E_ROT), _p(t["obra"]), Paragraph("Data", E_ROT), _p(_data(t["data"]))],
        [Paragraph("Empresa", E_ROT), _p(t["empresa"] or "-"), Paragraph("Preenchido por", E_ROT), _p(t["responsavel"] or "-")],
        [Paragraph("Preenchimento nº", E_ROT), _p(str(tid)), Paragraph("Pontuação", E_ROT), _p(f"{pontos} de {tm.PONTOS_MAX} pontos")],
    ]
    ti = Table(info, colWidths=[32 * mm, largura / 2 - 32 * mm, 32 * mm, largura / 2 - 32 * mm])
    ti.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), CINZA_CL),
        ("BACKGROUND", (2, 0), (2, -1), CINZA_CL),
        ("GRID", (0, 0), (-1, -1), 0.5, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(ti)
    story.append(Spacer(1, 6 * mm))

    # ---- resultado
    story.append(_secao("Resultado", largura))
    story.append(Spacer(1, 2 * mm))
    story.append(_grafico_faixas(pontos, largura))
    cor_txt = "#1F2937" if fx == "Médio" else "#FFFFFF"
    badge = Table(
        [[Paragraph(f'<font color="{cor_txt}"><b>Risco {fx.lower()}</b>: {escape(tm.SIGNIFICADO[fx])}</font>',
                    _estilo("bd", fontSize=10, leading=13))]],
        colWidths=[largura],
    )
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR_FAIXA[fx]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(badge)
    story.append(Spacer(1, 3 * mm))

    n_acoes = len(acoes)
    concl = int(acoes["fechada"].sum()) if n_acoes else 0
    venc = int(acoes["vencida"].sum()) if n_acoes else 0
    story.append(_kpis([
        (f"{len(sim)} de 17", "Respostas SIM", "#C62828" if sim else "#2E7D32"),
        (n_acoes, "Ações criadas", "#14532D"),
        (concl, "Ações concluídas", "#2E7D32"),
        (n_acoes - concl - venc, "Ações em aberto", "#1E88E5"),
        (venc, "Ações vencidas", "#C62828" if venc else "#6B7280"),
    ], largura))
    story.append(Spacer(1, 6 * mm))

    # ---- desvios apontados (resumo)
    story.append(_secao("Desvios apontados", largura))
    story.append(Spacer(1, 2 * mm))
    if not sim:
        story.append(Paragraph("Nenhum risco foi apontado neste preenchimento (nenhuma resposta SIM).", E_NOTA))
    else:
        th = lambda x, al=0: Paragraph(x, _estilo("th", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=al))
        linhas = [[th("Nº", TA_CENTER), th("Desvio apontado"), th("Grupo"), th("Pts", TA_CENTER), th("Ações", TA_CENTER), th("Situação das ações")]]
        c8 = _estilo("c8r", fontSize=8.5, alignment=TA_CENTER)
        for n in sorted(sim):
            grupo, txt, pts = tm.PERG[n]
            das = acoes[acoes["pergunta"] == n]
            if das.empty:
                situ = '<font color="#C62828"><b>Sem ação registrada</b></font>'
            else:
                partes = []
                nc, nv, na = int(das["fechada"].sum()), int(das["vencida"].sum()), int((~das["fechada"] & ~das["vencida"]).sum())
                if nv:
                    partes.append(f'<font color="#C62828"><b>{nv} vencida(s)</b></font>')
                if na:
                    partes.append(f'<font color="#1E88E5"><b>{na} em aberto</b></font>')
                if nc:
                    partes.append(f'<font color="#2E7D32"><b>{nc} concluída(s)</b></font>')
                situ = ", ".join(partes)
            linhas.append([
                Paragraph(str(n), c8), _p(txt), _p(grupo, E_CEL_PEQ), Paragraph(str(pts), c8),
                Paragraph(str(len(das)), c8), Paragraph(situ, E_CEL_PEQ),
            ])
        tr = Table(linhas, colWidths=[10 * mm, 78 * mm, 32 * mm, 11 * mm, 13 * mm, largura - 144 * mm], repeatRows=1)
        tr.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERMELHO),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERMELHO_CL]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(tr)
    story.append(PageBreak())

    # ---- perguntas e respostas
    story.append(_secao("Perguntas e respostas", largura))
    story.append(Spacer(1, 2 * mm))
    cab = [Paragraph(x, _estilo("th", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=al))
           for x, al in (("Nº", TA_CENTER), ("Pergunta", 0), ("Peso", TA_CENTER), ("Resposta", TA_CENTER), ("Pontos", TA_CENTER))]
    linhas = [cab]
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    for grupo in tm.GRUPOS:
        perguntas = [(n, g, txt, pts) for n, g, txt, pts in tm.PERGUNTAS if g == grupo]
        obtidos = sum(p for n, _, _, p in perguntas if n in sim)
        maximo = sum(p for _, _, _, p in perguntas)
        r = len(linhas)
        linhas.append([Paragraph(f"<b>{escape(grupo)}</b>  ·  {obtidos} de {maximo} pontos",
                                 _estilo("gr", fontSize=8.5, textColor=VERDE_ESC)), "", "", "", ""])
        estilos += [("SPAN", (0, r), (-1, r)), ("BACKGROUND", (0, r), (-1, r), VERDE_CL)]
        for n, _, txt, pts in perguntas:
            r = len(linhas)
            eh_sim = n in sim
            linhas.append([
                Paragraph(str(n), _estilo("n", fontSize=8.5, alignment=TA_CENTER)),
                _p(txt),
                Paragraph(str(pts), _estilo("pe", fontSize=8.5, alignment=TA_CENTER)),
                Paragraph('<font color="#C62828"><b>SIM</b></font>' if eh_sim else '<font color="#6B7280">NÃO</font>',
                          _estilo("re", fontSize=8.5, alignment=TA_CENTER)),
                Paragraph(f"<b>{pts}</b>" if eh_sim else "0", _estilo("po", fontSize=8.5, alignment=TA_CENTER)),
            ])
            if eh_sim:
                estilos.append(("BACKGROUND", (0, r), (-1, r), VERMELHO_CL))
    r = len(linhas)
    linhas.append(["", Paragraph("<b>Total</b>", E_CEL), "", "",
                   Paragraph(f"<b>{pontos} / {tm.PONTOS_MAX}</b>", _estilo("tt", fontSize=9, alignment=TA_CENTER))])
    estilos += [("BACKGROUND", (0, r), (-1, r), CINZA_CL), ("SPAN", (1, r), (3, r))]
    tp = Table(linhas, colWidths=[11 * mm, largura - 11 * mm - 16 * mm - 23 * mm - 21 * mm, 16 * mm, 23 * mm, 21 * mm], repeatRows=1)
    tp.setStyle(TableStyle(estilos))
    story.append(tp)

    obs = (t["observacao"] or "").strip() if isinstance(t["observacao"], str) else ""
    if obs:
        story.append(Spacer(1, 5 * mm))
        story.append(_secao("Observações", largura))
        story.append(Spacer(1, 2 * mm))
        story.append(_p(obs, E_NORMAL))

    # ---- detalhamento das ações
    if n_acoes:
        story.append(CondPageBreak(85 * mm))  # evita o título sozinho no fim da página
        story.append(Spacer(1, 8 * mm))
        story.append(_secao("Detalhamento das ações", largura))
        story.append(Spacer(1, 3 * mm))
        for n in sorted(sim):
            das_acoes = acoes[acoes["pergunta"] == n]
            if das_acoes.empty:
                continue
            grupo, txt, pts = tm.PERG[n]
            cab_d = Table([[Paragraph(f"<b>{n}. {escape(txt)}</b>  ({pts} pt{'s' if pts > 1 else ''}) · {escape(grupo)}",
                                      _estilo("cd", fontSize=9, textColor=colors.HexColor('#7F1D1D')))]], colWidths=[largura])
            cab_d.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), VERMELHO_CL),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]))
            primeiro = True
            for _, a in das_acoes.iterrows():
                bloco = _cartao_acao(a, tm.listar_fotos(int(a["id"])), largura)
                story.append(KeepTogether(([cab_d, Spacer(1, 1.5 * mm)] if primeiro else []) + bloco))
                primeiro = False

    # ---- assinaturas
    story.append(Spacer(1, 6 * mm))
    story.append(KeepTogether([_assinaturas(largura)]))

    subtitulo = f"Obra: {t['obra']}  ·  Data: {_data(t['data'])}  ·  Preenchimento nº {tid}"
    return _montar(story, A4, "Termômetro de Segurança da Obra", subtitulo)


def nome_arquivo_termometro(tid: int) -> str:
    termo = tm.listar()
    t = termo[termo["id"] == tid].iloc[0]
    return f"Termometro_{_slug(t['obra'])}_{pd.Timestamp(t['data']):%Y-%m-%d}_n{tid}.pdf"


def assinatura_termometro(tid: int):
    """Resumo do que entra no relatório; muda quando ações ou fotos são alteradas."""
    acoes = tm.listar_acoes()
    acoes = acoes[acoes["termometro_id"] == tid].sort_values("id")
    return tuple(
        (int(a["id"]), a["status"], str(a["acao"]), str(a["prazo"]), int(a["fotos_antes"]), int(a["fotos_depois"]))
        for _, a in acoes.iterrows()
    )


# ======================================================================
# DESVIOS DE INSPEÇÃO (ACOMPANHAMENTO)
# ======================================================================
def _barras_horizontais(titulo, dados, largura, cor):
    """Gráfico de barras horizontais simples. dados: lista de (rótulo, valor)."""
    alt_lin = 7 * mm
    h = len(dados) * alt_lin + 9 * mm
    d = Drawing(largura, h)
    d.add(String(0, h - 4 * mm, titulo, fontName="Helvetica-Bold", fontSize=9, fillColor=TEXTO))
    rot_w = 44 * mm
    maxv = max(v for _, v in dados) or 1
    area = largura - rot_w - 12 * mm
    for i, (rot, v) in enumerate(dados):
        y = h - 9 * mm - (i + 1) * alt_lin + 1.3 * mm
        d.add(String(rot_w - 2 * mm, y + 1.6 * mm, rot[:26], textAnchor="end", fontName="Helvetica", fontSize=8, fillColor=TEXTO))
        w = area * v / maxv
        d.add(Rect(rot_w, y, max(w, 0.6 * mm), alt_lin - 2.8 * mm, fillColor=cor, strokeColor=None))
        d.add(String(rot_w + w + 1.8 * mm, y + 1.6 * mm, str(v), fontName="Helvetica-Bold", fontSize=8, fillColor=TEXTO))
    return d


def pdf_desvios(df: pd.DataFrame, obra: str, situacao: str, ini, fim) -> bytes:
    """Relatório consolidado dos desvios de inspeção já filtrados (df vem de banco.listar())."""
    d = df.copy()
    d["situacao"] = "Em aberto"
    d.loc[d["vencido"], "situacao"] = "Vencido"
    d.loc[d["fechado"], "situacao"] = "Concluído"
    hoje = pd.Timestamp.today().normalize()
    d["dias_atraso"] = (hoje - d["prazo"]).dt.days.where(d["vencido"])
    d = d.sort_values(["data", "id"])

    pagesize = landscape(A4)
    largura = pagesize[0] - 2 * MARGEM
    story = []

    total = len(d)
    abertos = int((d["situacao"] == "Em aberto").sum())
    vencidos = int((d["situacao"] == "Vencido").sum())
    concl = int((d["situacao"] == "Concluído").sum())
    tempo = d["dias_para_fechar"].mean()

    story.append(_kpis([
        (total, "Desvios no relatório", "#14532D"),
        (abertos, "Em aberto", "#1E88E5"),
        (vencidos, "Vencidos", "#C62828" if vencidos else "#6B7280"),
        (concl, "Concluídos", "#2E7D32"),
        ("-" if pd.isna(tempo) else f"{tempo:.1f} dias".replace(".", ","), "Tempo médio para fechar", "#6B7280"),
    ], largura))
    story.append(Spacer(1, 6 * mm))

    # ---- resumo por empreiteira e gráfico por categoria
    story.append(_secao("Visão geral", largura))
    story.append(Spacer(1, 3 * mm))
    cab = [Paragraph(x, _estilo("th", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=al))
           for x, al in (("Empreiteira", 0), ("Total", TA_CENTER), ("Em aberto", TA_CENTER), ("Vencidos", TA_CENTER),
                         ("Concluídos", TA_CENTER), ("% concluídos", TA_CENTER))]
    linhas = [cab]
    resumo = d.groupby("empreiteira", dropna=False)
    for emp, g in sorted(resumo, key=lambda kv: -len(kv[1])):
        n = len(g)
        c = int((g["situacao"] == "Concluído").sum())
        centro8 = _estilo("c8", fontSize=8.5, alignment=TA_CENTER)
        linhas.append([
            _p(emp if isinstance(emp, str) else "-"), Paragraph(str(n), centro8),
            Paragraph(str(int((g["situacao"] == "Em aberto").sum())), centro8),
            Paragraph(str(int((g["situacao"] == "Vencido").sum())), centro8),
            Paragraph(str(c), centro8), Paragraph(f"{100 * c / n:.0f}%", centro8),
        ])
    esq_w = 150 * mm
    te = Table(linhas, colWidths=[56 * mm, 16 * mm, 20 * mm, 18 * mm, 20 * mm, 20 * mm], repeatRows=1)
    te.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CL]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    cats = d["categoria"].fillna("-").value_counts().head(8)
    grafico = _barras_horizontais("Desvios por categoria", list(cats.items()), largura - esq_w - 8 * mm, VERDE)
    lado = Table([[te, grafico]], colWidths=[esq_w + 8 * mm, largura - esq_w - 8 * mm])
    lado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 8 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    story.append(lado)

    # ---- pendências vencidas
    venc = d[d["situacao"] == "Vencido"].sort_values("dias_atraso", ascending=False)
    story.append(Spacer(1, 8 * mm))
    story.append(_secao("Pendências vencidas", largura))
    story.append(Spacer(1, 3 * mm))
    if venc.empty:
        story.append(Paragraph("Nenhuma pendência vencida neste relatório.", E_NOTA))
    else:
        th = lambda x, al=0: Paragraph(x, _estilo("th", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white, alignment=al))
        linhas = [[th("Nº", TA_CENTER), th("Data", TA_CENTER), th("Obra"), th("Local"), th("Categoria"), th("Gravidade", TA_CENTER),
                   th("Empreiteira"), th("Responsável"), th("Prazo", TA_CENTER), th("Atraso (dias)", TA_CENTER)]]
        for _, r in venc.iterrows():
            linhas.append([
                Paragraph(str(int(r["id"])), _estilo("x", fontSize=8, alignment=TA_CENTER)),
                Paragraph(_data(r["data"]), _estilo("x", fontSize=8, alignment=TA_CENTER)),
                _p(r["obra"], E_CEL_PEQ), _p(r["local"], E_CEL_PEQ), _p(r["categoria"], E_CEL_PEQ),
                Paragraph(escape(str(r["gravidade"] or "-")), _estilo("x", fontSize=8, alignment=TA_CENTER)),
                _p(r["empreiteira"], E_CEL_PEQ), _p(r["responsavel"], E_CEL_PEQ),
                Paragraph(_data(r["prazo"]), _estilo("x", fontSize=8, alignment=TA_CENTER)),
                Paragraph(f'<font color="#C62828"><b>{int(r["dias_atraso"])}</b></font>', _estilo("x", fontSize=8, alignment=TA_CENTER)),
            ])
        tv = Table(linhas, colWidths=[11 * mm, 20 * mm, 36 * mm, 36 * mm, 34 * mm, 20 * mm, 36 * mm, 30 * mm, 20 * mm, 24 * mm], repeatRows=1)
        tv.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERMELHO),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERMELHO_CL]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tv)

    # ---- detalhamento
    story.append(Spacer(1, 8 * mm))
    story.append(_secao("Detalhamento dos desvios", largura))
    story.append(Spacer(1, 3 * mm))
    th = lambda x, al=0: Paragraph(x, _estilo("th", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white, alignment=al))
    linhas = [[th("Nº", TA_CENTER), th("Data", TA_CENTER), th("Obra"), th("Local"), th("Categoria"), th("Grav.", TA_CENTER),
               th("Empreiteira"), th("Responsável"), th("Prazo", TA_CENTER), th("Situação", TA_CENTER), th("Descrição e ação corretiva")]]
    c7 = _estilo("c7", fontSize=7.5, leading=9.5, alignment=TA_CENTER)
    for _, r in d.iterrows():
        hex_sit = HEX_SITUACAO.get(r["situacao"], "#1F2937")
        desc = escape(str(r["descricao"] or "")).replace("\n", "<br/>")
        acao = escape(str(r["acao_corretiva"] or "")).replace("\n", "<br/>")
        texto = desc + (f'<br/><font color="#6B7280"><i>Ação: {acao}</i></font>' if acao else "")
        linhas.append([
            Paragraph(str(int(r["id"])), c7), Paragraph(_data(r["data"]), c7),
            _p(r["obra"], E_CEL_PEQ), _p(r["local"], E_CEL_PEQ), _p(r["categoria"], E_CEL_PEQ),
            Paragraph(escape(str(r["gravidade"] or "-")), c7),
            _p(r["empreiteira"], E_CEL_PEQ), _p(r["responsavel"], E_CEL_PEQ),
            Paragraph(_data(r["prazo"]), c7),
            Paragraph(f'<font color="{hex_sit}"><b>{r["situacao"]}</b></font>', c7),
            Paragraph(texto, E_CEL_PEQ),
        ])
    colw = [8, 16, 25, 24, 25, 13, 27, 23, 16, 18]
    colw = [c * mm for c in colw] + [largura - sum(c * mm for c in colw)]
    td = Table(linhas, colWidths=colw, repeatRows=1)
    td.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CL]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(td)

    periodo = f"{_data(ini)} a {_data(fim)}"
    subtitulo = f"Obra: {obra}  ·  Situação: {situacao}  ·  Período: {periodo}"
    return _montar(story, pagesize, "Relatório de Desvios de Inspeção", subtitulo)


def nome_arquivo_desvios(obra: str, ini, fim) -> str:
    return f"Desvios_{_slug(obra)}_{pd.Timestamp(ini):%Y-%m-%d}_a_{pd.Timestamp(fim):%Y-%m-%d}.pdf"