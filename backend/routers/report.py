"""
Router de relatórios — gera PDFs executivos com os resultados da análise APM.
Usa ReportLab para geração server-side sem dependências de browser.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/report", tags=["Report"])


# ─── Schema ───────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    meta:         Dict[str, Any]
    fit:          Dict[str, Any]
    rul:          Dict[str, Any]
    ca:           Dict[str, Any]
    audit:        Dict[str, Any]
    ml:           Dict[str, Any]
    prescriptive: Dict[str, Any] = Field(default_factory=dict)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt(val: Any, decimals: int = 2, suffix: str = "") -> str:
    try:
        return f"{float(val):.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(val) if val is not None else "—"


def _safe(d: dict, *keys, default="—"):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d not in (None, {}, []) else default


def _md_inline(text: str) -> str:
    """Converte markdown inline (**bold**, *italic*) para XML do ReportLab."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*([^*]+?)\*',  r'<i>\1</i>', text)
    # Escapa & que não faça parte de entidade XML
    text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', text)
    return text


def _md_to_elements(text: str, body_s, section_s, subsection_s, hr_fn, tbl_fn):
    """Converte texto markdown simples em lista de flowables ReportLab."""
    import re
    from reportlab.platypus import Spacer
    from reportlab.lib.units import cm

    elements = []
    lines    = text.split("\n")
    i        = 0

    while i < len(lines):
        raw  = lines[i]
        line = raw.strip()
        i   += 1

        if not line:
            elements.append(Spacer(1, 0.12*cm))
            continue

        # H1: # Título
        if line.startswith("# "):
            elements.append(Paragraph(_md_inline(line[2:].strip()), section_s))
            continue

        # H2: ## Título
        if line.startswith("## "):
            elements.append(Paragraph(_md_inline(line[3:].strip()), subsection_s))
            continue

        # H3: ### Título  ou  **Título** (negrito sozinho na linha)
        if line.startswith("### "):
            elements.append(Paragraph(_md_inline(line[4:].strip()), subsection_s))
            continue

        if re.match(r'^\*\*[^*].+\*\*$', line):
            elements.append(Paragraph(_md_inline(line), subsection_s))
            continue

        # Separador horizontal
        if re.match(r'^[-*_]{3,}$', line):
            elements.append(hr_fn())
            continue

        # Bloco de tabela markdown  | col | col |
        if line.startswith("|"):
            from reportlab.platypus import Paragraph as _Para
            tbl_lines = [line]
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1
            # Remove linhas separadoras |---|---|
            tbl_lines = [l for l in tbl_lines
                         if not re.match(r'^\|[-:\s|]+\|$', l)]
            if tbl_lines:
                rows = []
                for tl in tbl_lines:
                    cells = [_Para(_md_inline(c.strip()), body_s)
                             for c in tl.strip("|").split("|")]
                    rows.append(cells)
                if len(rows) >= 1:
                    # normaliza número de colunas
                    ncols = max(len(r) for r in rows)
                    rows  = [r + [_Para("", body_s)] * (ncols - len(r)) for r in rows]
                    header = rows[0]
                    data   = rows[1:] if len(rows) > 1 else [[_Para("", body_s)] * ncols]
                    elements.append(tbl_fn(header, data))
            continue

        # Parágrafo normal
        elements.append(Paragraph(_md_inline(line), body_s))

    return elements


# ─── Geração do PDF ───────────────────────────────────────────────────────────

def _build_pdf(req: ReportRequest) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )

    PAGE_W, PAGE_H = A4
    MARGIN_L = 2 * cm
    MARGIN_R = 2 * cm
    HEADER_H = 2.6 * cm

    meta  = req.meta
    fit   = req.fit
    rul   = req.rul
    ca    = req.ca
    audit = req.audit
    ml    = req.ml
    presc = req.prescriptive
    best  = fit.get("best", {})

    # ── Paleta ────────────────────────────────────────────────────────────────
    DARK_BLUE = colors.HexColor("#003366")
    MID_BLUE  = colors.HexColor("#005F9E")
    ACCENT    = colors.HexColor("#0088CC")
    ROW_ALT   = colors.HexColor("#EAF4FB")
    BLACK     = colors.HexColor("#1A1A1A")
    GRAY      = colors.HexColor("#555555")
    WHITE     = colors.white
    GREEN     = colors.HexColor("#0F6B3A")
    ORANGE    = colors.HexColor("#B45309")
    RED_C     = colors.HexColor("#991B1B")
    BLUE_C    = colors.HexColor("#1D4ED8")

    URGENCY_COLOR = {
        "Crítica": RED_C, "Alta": ORANGE,
        "Média": BLUE_C,  "Baixa": GREEN,
    }

    # ── Cabeçalho em todas as páginas ─────────────────────────────────────────
    def _draw_header(canvas, doc):
        canvas.saveState()
        x0, xf = MARGIN_L, PAGE_W - MARGIN_R
        w = xf - x0

        bar_y = PAGE_H - 1.1 * cm
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(x0, bar_y - 0.55*cm, w, 0.65*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(WHITE)
        canvas.drawString(x0 + 0.2*cm, bar_y - 0.38*cm, "APM ANALYTICS  ·  AR²")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(xf - 0.2*cm, bar_y - 0.38*cm, f"Página {doc.page}")

        bar2_y = bar_y - 0.55*cm
        canvas.setFillColor(ACCENT)
        canvas.rect(x0, bar2_y - 0.5*cm, w, 0.5*cm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(WHITE)
        canvas.drawString(x0 + 0.2*cm, bar2_y - 0.34*cm,
                          "Relatório de Confiabilidade · Manutenção Preditiva e Prescritiva · ISO 14224")
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(xf - 0.2*cm, bar2_y - 0.34*cm,
                               datetime.now().strftime("%d/%m/%Y %H:%M"))

        bar3_y = bar2_y - 0.5*cm
        canvas.setFillColor(ROW_ALT)
        canvas.rect(x0, bar3_y - 0.46*cm, w, 0.46*cm, fill=1, stroke=0)
        fields = [
            ("TAG:", meta.get("tag", "—"), 0.0),
            ("Equipamento:", meta.get("tipo_equipamento", "—"), 3.2),
            ("Fabricante:", meta.get("fabricante") or "—", 9.5),
            ("Horímetro:", f"{meta.get('horimetro_atual', 0):.0f} h", 13.5),
        ]
        for label, value, offset in fields:
            canvas.setFont("Helvetica-Bold", 7)
            canvas.setFillColor(DARK_BLUE)
            canvas.drawString(x0 + offset*cm, bar3_y - 0.31*cm, label)
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(BLACK)
            label_w = canvas.stringWidth(label, "Helvetica-Bold", 7) / 28.35
            canvas.drawString(x0 + (offset + label_w + 0.15)*cm, bar3_y - 0.31*cm, str(value))

        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(0.8)
        canvas.line(x0, bar3_y - 0.5*cm, xf, bar3_y - 0.5*cm)
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=HEADER_H + 0.8*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("APMTitle", parent=styles["Title"],
        fontSize=20, textColor=DARK_BLUE, spaceAfter=2, fontName="Helvetica-Bold")
    section_style = ParagraphStyle("APMSection", parent=styles["Heading2"],
        fontSize=11, textColor=MID_BLUE, spaceBefore=16, spaceAfter=6,
        fontName="Helvetica-Bold")
    subsection_style = ParagraphStyle("APMSub2", parent=styles["Heading3"],
        fontSize=10, textColor=DARK_BLUE, spaceBefore=10, spaceAfter=4,
        fontName="Helvetica-Bold")
    body_style = ParagraphStyle("APMBody", parent=styles["Normal"],
        fontSize=9, textColor=BLACK, spaceAfter=5, leading=13)
    caption_style = ParagraphStyle("APMCaption", parent=styles["Normal"],
        fontSize=8, textColor=GRAY, spaceAfter=2)
    alert_style = ParagraphStyle("APMAlert", parent=styles["Normal"],
        fontSize=9, textColor=RED_C, spaceAfter=3, fontName="Helvetica-Bold")

    def _hr():
        return HRFlowable(width="100%", thickness=0.8, color=ACCENT,
                          spaceAfter=4, spaceBefore=2)

    def _tbl(headers, rows, col_widths=None, header_color=None):
        hc = header_color or ACCENT
        data = [headers] + rows
        tbl  = Table(data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  hc),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  8),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  5),
            ("TOPPADDING",    (0, 0), (-1, 0),  5),
            ("BACKGROUND",    (0, 1), (-1, -1), WHITE),
            ("TEXTCOLOR",     (0, 1), (-1, -1), BLACK),
            ("FONTSIZE",      (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#AACCDD")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ]))
        return tbl

    story = []
    story.append(Spacer(1, 0.2*cm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. IDENTIFICAÇÃO DO ATIVO
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Identificação do Ativo", section_style))
    id_rows = [
        ["TAG Operacional",          meta.get("tag", "—"),
         "Tipo de Equipamento",       meta.get("tipo_equipamento", "—")],
        ["Número de Série",           meta.get("numero_serie") or "—",
         "Setor / Unidade",           meta.get("setor") or "—"],
        ["Fabricante",                meta.get("fabricante") or "—",
         "Modelo / Referência",       meta.get("modelo") or "—"],
        ["Data de Instalação",        meta.get("data_instalacao") or "—",
         "Classificação Ambiental",   meta.get("classificacao_ambiental") or "—"],
        ["Responsável Manutenção",    meta.get("responsavel_manutencao") or "—",
         "Data do Estudo",            meta.get("data_estudo") or "—"],
        ["Horímetro Atual",           f"{meta.get('horimetro_atual', 0):.0f} h",
         "Gerado em",                 datetime.now().strftime("%d/%m/%Y %H:%M")],
    ]
    tbl_id = Table(id_rows, colWidths=[3.8*cm, 5.2*cm, 4.0*cm, 4.5*cm])
    tbl_id.setStyle(TableStyle([
        ("TEXTCOLOR",     (0, 0), (-1, -1), BLACK),
        ("TEXTCOLOR",     (0, 0), (0, -1),  MID_BLUE),
        ("TEXTCOLOR",     (2, 0), (2, -1),  MID_BLUE),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("FONTNAME",      (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",      (2, 0), (2, -1),  "Helvetica-Bold"),
        ("BACKGROUND",    (0, 0), (-1, -1), ROW_ALT),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [ROW_ALT, colors.HexColor("#F0F8FF")]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#AACCDD")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl_id)
    story.append(Spacer(1, 0.3*cm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. SAÚDE E RUL
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(_hr())
    story.append(Paragraph("Saúde e Vida Útil Remanescente (RUL)", section_style))

    health_pct = rul.get("r_current", 0) * 100
    rul_time   = rul.get("rul_time", 0)
    rul_p10    = rul.get("rul_p10", rul_time * 0.7)
    rul_p90    = rul.get("rul_p90", rul_time * 1.3)
    horizonte  = meta.get("horimetro_atual", 0) + rul_time

    story.append(_tbl(
        ["Indicador", "Valor", "Interpretação"],
        [
            ["Confiabilidade R(t₀)",    f"{health_pct:.1f}%",
             "Probabilidade de operação no horímetro atual"],
            ["RUL — Vida Residual",     f"+{rul_time:.0f} h",
             "Tempo até atingir limiar de confiabilidade"],
            ["Horizonte de Intervenção", f"{horizonte:.0f} h",
             "Horímetro estimado para manutenção preventiva"],
            ["IC 80% (Bootstrap)",      f"[{rul_p10:.0f} — {rul_p90:.0f}] h",
             "Intervalo de confiança — 300 reamostragens"],
        ],
        col_widths=[4.5*cm, 3.5*cm, 9.5*cm],
    ))
    story.append(Spacer(1, 0.3*cm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. MODELOS PARAMÉTRICOS — LDA
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(_hr())
    story.append(Paragraph("Análise de Dados de Vida (LDA) — Modelos Paramétricos", section_style))
    story.append(Paragraph(
        f"Melhor modelo: <b>{best.get('model_name','—')}</b>  ·  AICc = {_fmt(best.get('aicc'))}",
        body_style,
    ))

    param_rows = []
    for p, label in [("beta","β (forma)"),("eta","η (escala/vida car.)"),
                     ("mu","μ"),("sigma","σ"),("Lambda","λ (taxa)"),("mttf","MTTF")]:
        v = best.get(p)
        if v is not None:
            param_rows.append([label, _fmt(v, 4)])
    if param_rows:
        story.append(_tbl(["Parâmetro","Valor"], param_rows, col_widths=[5*cm, 5*cm]))

    ranking = fit.get("ranking", [])
    if ranking:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("Ranking AICc dos Modelos", caption_style))
        story.append(_tbl(
            ["Pos.", "Modelo", "AICc", "ΔAICc"],
            [[str(i+1), r.get("model",""), _fmt(r.get("aicc")),
              _fmt(r.get("aicc",0) - ranking[0].get("aicc",0))]
             for i, r in enumerate(ranking)],
            col_widths=[1.5*cm, 5*cm, 3.5*cm, 3.5*cm],
        ))
    story.append(Spacer(1, 0.3*cm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. CROW-AMSAA / NHPP
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(_hr())
    story.append(Paragraph("Análise de Degradação — Crow-AMSAA / NHPP", section_style))
    story.append(_tbl(
        ["Parâmetro", "Valor", "Interpretação"],
        [
            ["β (Crow-AMSAA)", _fmt(ca.get("beta", "—"), 4),
             "β > 1: degradação crescente | β < 1: burn-in | β ≈ 1: aleatório"],
            ["λ (taxa de referência)", _fmt(ca.get("lambda", "—"), 6),
             "Intensidade de falha no ponto de referência"],
            ["Regime", str(ca.get("regime", "—")), ""],
        ],
        col_widths=[4.5*cm, 3.5*cm, 9.5*cm],
    ))
    story.append(Spacer(1, 0.3*cm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. MACHINE LEARNING — SCORE DE RISCO
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(_hr())
    story.append(Paragraph("Machine Learning Preditivo", section_style))

    risk    = ml.get("risk", {})
    trend   = ml.get("trend", {})
    anom    = ml.get("anomalies", {})
    metrics = ml.get("metrics", {})
    forecast= ml.get("forecast", {})

    # Score de risco
    story.append(Paragraph("Score de Risco Integrado", subsection_style))
    risk_score = risk.get("score", 0)
    risk_class = risk.get("classification", "—")
    risk_color = URGENCY_COLOR.get(risk_class, BLUE_C)

    comps = risk.get("components", {})
    risk_rows = [
        ["Score de Risco",         str(risk_score) + "/100",   risk_class],
        ["Ação Recomendada",       risk.get("action", "—"),    ""],
        ["Confiabilidade R(t)",    _fmt(comps.get("reliability_rt", 0), 1) + "/30 pts",
         "Vida útil consumida"],
        ["Tendência TBF",          _fmt(comps.get("tendency_tbf", 0), 1) + "/30 pts",
         "Degradação temporal"],
        ["Anomalias (IF)",         _fmt(comps.get("anomalies_if", 0), 1) + "/25 pts",
         "Eventos anômalos"],
        ["Proximidade TBF ML",     _fmt(comps.get("proximity_ml", 0), 1) + "/15 pts",
         "Próximo ciclo vs. média"],
    ]
    tbl_risk = _tbl(["Indicador", "Valor", "Detalhe"], risk_rows,
                    col_widths=[5*cm, 4*cm, 8.5*cm])
    # Destaca linha do score com cor de urgência
    tbl_risk.setStyle(TableStyle([
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#FEF3C7")),
        ("TEXTCOLOR",  (0, 1), (-1, 1), ORANGE),
        ("FONTNAME",   (0, 1), (-1, 1), "Helvetica-Bold"),
    ]))
    story.append(tbl_risk)
    story.append(Spacer(1, 0.2*cm))

    # Tendência
    story.append(Paragraph("Tendência e Predição", subsection_style))
    story.append(_tbl(
        ["Indicador", "Valor", "Detalhe"],
        [
            ["Tipo de Tendência",   trend.get("trend_type", "—"),
             f"slope = {_fmt(trend.get('slope', 0), 3)} h/ciclo"],
            ["Taxa de Degradação",  f"{_fmt(trend.get('degradation_rate', 0), 2)}%/ciclo", ""],
            ["R² da Tendência",     _fmt(trend.get("r_squared", 0), 4), ""],
            ["Próximo TBF (RF)",    f"{forecast.get('next_tbf', 0):.0f} h"
             if forecast.get("next_tbf") else "—", "Random Forest"],
            ["R² do Modelo",        _fmt(metrics.get("r2", 0), 4),
             f"MAE = {_fmt(metrics.get('mae', 0), 1)} h"],
        ],
        col_widths=[5*cm, 4*cm, 8.5*cm],
    ))
    story.append(Spacer(1, 0.2*cm))

    # Anomalias
    anom_count = anom.get("count", 0)
    story.append(Paragraph("Detecção de Anomalias — Isolation Forest", subsection_style))
    story.append(_tbl(
        ["Indicador", "Valor"],
        [
            ["Anomalias detectadas", str(anom_count)],
            ["% do histórico",
             f"{anom_count / max(len(anom.get('values', [1])), 1) * 100:.1f}%"],
        ],
        col_widths=[6*cm, 6*cm],
    ))
    if anom_count > 0 and anom.get("values"):
        anom_rows = [
            [str(idx), f"{val:.0f} h"]
            for idx, val in zip(anom.get("indices", []), anom.get("values", []))
        ]
        story.append(_tbl(["Ciclo Anômalo", "TBF (h)"], anom_rows[:10],
                          col_widths=[4*cm, 4*cm]))
    story.append(Spacer(1, 0.3*cm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. MANUTENÇÃO PRESCRITIVA (se disponível)
    # ═══════════════════════════════════════════════════════════════════════════
    if presc and presc.get("acoes"):
        story.append(_hr())
        story.append(Paragraph("Manutenção Prescritiva — Plano de Ação ISO 14224", section_style))

        nivel    = presc.get("nivel_urgencia", "—")
        janela   = presc.get("janela_intervencao", "—")
        hs       = presc.get("proxima_intervencao_h")
        sumario  = presc.get("sumario_executivo", "")
        ia_ativa = presc.get("ia_disponivel", False)

        fonte = "Agente Claude (claude-sonnet-4-6 + tool_use)" if ia_ativa else "Expert System (regras ISO 14224)"
        urgency_color_pdf = URGENCY_COLOR.get(nivel, BLUE_C)

        story.append(_tbl(
            ["Parâmetro", "Valor"],
            [
                ["Nível de Urgência",       nivel],
                ["Janela de Intervenção",   janela],
                ["Horas até Intervenção",   f"{hs:.0f} h" if hs else "—"],
                ["Fonte da Prescrição",     fonte],
            ],
            col_widths=[5*cm, 12.5*cm],
            header_color=urgency_color_pdf,
        ))

        if sumario:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph("<b>Sumário Executivo:</b>", body_style))
            story.append(Paragraph(sumario, body_style))

        # Diagnóstico técnico — renderiza markdown corretamente
        diag = presc.get("diagnostico", "")
        if diag:
            story.append(Spacer(1, 0.25*cm))
            story.append(Paragraph("<b>Diagnóstico Técnico</b>", subsection_style))
            story.append(Spacer(1, 0.1*cm))
            story.extend(_md_to_elements(
                diag, body_style, section_style, subsection_style, _hr, _tbl,
            ))

        # Tabela de ações priorizadas
        acoes = presc.get("acoes", [])
        if acoes:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("Plano de Ações Priorizadas", subsection_style))
            acao_rows = []
            for a in acoes:
                acao_rows.append([
                    f"#{a.get('prioridade','—')}",
                    a.get("subcomponente", "—"),
                    a.get("modo_falha", "—"),
                    a.get("criticidade", "—"),
                    a.get("janela_intervencao", "—"),
                    f"{a.get('ttr_esperado_h','—')} h" if a.get("ttr_esperado_h") else "—",
                ])
            story.append(_tbl(
                ["Pri.", "Subcomponente", "Modo de Falha", "Criticidade", "Janela", "TTR Est."],
                acao_rows,
                col_widths=[1.2*cm, 3.5*cm, 4.0*cm, 2.2*cm, 4.5*cm, 2.1*cm],
            ))

            # Detalhes das ações (ações críticas/altas)
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph("Detalhes das Ações Críticas e de Alta Prioridade", subsection_style))
            for a in acoes:
                if a.get("criticidade") not in ("Alta", "Crítica") and a.get("prioridade", 99) > 3:
                    continue
                KeepTogether([])
                story.append(Paragraph(
                    f"<b>#{a.get('prioridade')} — {a.get('subcomponente','—')} "
                    f"· {a.get('modo_falha','—')}</b>",
                    body_style,
                ))
                detail_rows = [
                    ["Causa Raiz",       a.get("causa_raiz", "—")],
                    ["Mecanismo",        a.get("mecanismo", "—")],
                    ["Fronteira",        a.get("boundary", "—")],
                    ["Ação Recomendada", a.get("acao_recomendada", "—")],
                    ["Justificativa",    a.get("justificativa", "—")],
                    ["Custo Relativo",   f"{a.get('custo_relativo', 1.0):.1f}×"],
                ]
                story.append(_tbl(["Campo", "Valor"], detail_rows,
                                  col_widths=[3.5*cm, 14.0*cm]))
                story.append(Spacer(1, 0.15*cm))

        story.append(Spacer(1, 0.3*cm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. AUDITORIA ESTATÍSTICA
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(_hr())
    story.append(Paragraph("Auditoria Estatística dos Dados", section_style))

    n_total  = audit.get("n_total", "—")
    n_fail   = audit.get("n_failures", "—")
    n_cens   = audit.get("n_censored", "—")
    cens_pct = audit.get("censoring_pct")
    p_ad     = audit.get("p_value_ad")
    kolm     = audit.get("kolmogorov_smirnov")

    story.append(_tbl(
        ["Métrica", "Valor"],
        [
            ["Total de registros",        str(n_total)],
            ["Falhas confirmadas",         str(n_fail)],
            ["Censuras",                   f"{n_cens} ({cens_pct:.1f}%)" if cens_pct else str(n_cens)],
            ["p-valor Anderson-Darling",   _fmt(p_ad, 4) if p_ad else "—"],
            ["Estatística K-S",            _fmt(kolm, 4) if kolm else "—"],
        ],
        col_widths=[7*cm, 5*cm],
    ))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8*cm))
    story.append(_hr())
    story.append(Paragraph(
        f"Gerado automaticamente pelo APM Analytics (AR²) — "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')} — ISO 14224:2016",
        caption_style,
    ))
    story.append(Paragraph(
        "Este relatório é de uso interno. Os modelos são calibrados com dados históricos do ativo.",
        caption_style,
    ))

    doc.build(story, onFirstPage=_draw_header, onLaterPages=_draw_header)
    return buf.getvalue()


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/pdf", summary="Gera relatório PDF executivo")
def generate_pdf(req: ReportRequest) -> Response:
    pdf_bytes = _build_pdf(req)
    tag = req.meta.get("tag", "ativo").replace(" ", "_")
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"APM_Relatorio_{tag}_{date_str}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
