"""
Router de relatórios — gera PDFs executivos com os resultados da análise APM.
Usa ReportLab para geração server-side sem dependências de browser.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/report", tags=["Report"])


# ─── Schema ───────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    meta:  Dict[str, Any]
    fit:   Dict[str, Any]
    rul:   Dict[str, Any]
    ca:    Dict[str, Any]
    audit: Dict[str, Any]
    ml:    Dict[str, Any]


# ─── Helpers de formatação ────────────────────────────────────────────────────

def _fmt(val: Any, decimals: int = 2, suffix: str = "") -> str:
    try:
        return f"{float(val):.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(val) if val is not None else "—"


# ─── Geração do PDF ───────────────────────────────────────────────────────────

def _build_pdf(req: ReportRequest) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    PAGE_W, PAGE_H = A4
    MARGIN_L = 2 * cm
    MARGIN_R = 2 * cm
    HEADER_H = 2.6 * cm   # altura reservada para o cabeçalho

    meta  = req.meta
    fit   = req.fit
    rul   = req.rul
    ca    = req.ca
    audit = req.audit
    ml    = req.ml
    best  = fit.get("best", {})

    # ── Função de cabeçalho — 3 linhas em todas as páginas ───────────────────
    def _draw_header(canvas, doc):
        canvas.saveState()

        C_BAR   = colors.HexColor("#003366")
        C_SUB   = colors.HexColor("#0088CC")
        C_TEXT  = colors.HexColor("#FFFFFF")
        C_LIGHT = colors.HexColor("#E0EEF8")
        C_DARK  = colors.HexColor("#1A1A1A")
        C_LINE  = colors.HexColor("#0088CC")

        x0 = MARGIN_L
        xf = PAGE_W - MARGIN_R
        w  = xf - x0

        # ── Linha 1: barra azul escura — "APM ANALYTICS" + nº página ─────────
        bar_y = PAGE_H - 1.1 * cm
        canvas.setFillColor(C_BAR)
        canvas.rect(x0, bar_y - 0.55*cm, w, 0.65*cm, fill=1, stroke=0)

        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(C_TEXT)
        canvas.drawString(x0 + 0.2*cm, bar_y - 0.38*cm, "APM ANALYTICS")

        page_str = f"Página {doc.page}"
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(xf - 0.2*cm, bar_y - 0.38*cm, page_str)

        # ── Linha 2: fundo azul médio — título do relatório ───────────────────
        bar2_y = bar_y - 0.55*cm
        canvas.setFillColor(C_SUB)
        canvas.rect(x0, bar2_y - 0.5*cm, w, 0.5*cm, fill=1, stroke=0)

        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(C_TEXT)
        canvas.drawString(
            x0 + 0.2*cm, bar2_y - 0.34*cm,
            "Relatório de Confiabilidade e Manutenção Preditiva",
        )

        # data de geração à direita
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(
            xf - 0.2*cm, bar2_y - 0.34*cm,
            datetime.now().strftime("%d/%m/%Y %H:%M"),
        )

        # ── Linha 3: fundo claro — identificação do ativo ─────────────────────
        bar3_y = bar2_y - 0.5*cm
        canvas.setFillColor(C_LIGHT)
        canvas.rect(x0, bar3_y - 0.46*cm, w, 0.46*cm, fill=1, stroke=0)

        tag   = meta.get("tag", "—")
        tipo  = meta.get("tipo_equipamento", "—")
        serie = meta.get("numero_serie", "—")
        horo  = meta.get("horimetro_atual", 0)

        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(C_BAR)
        canvas.drawString(x0 + 0.2*cm, bar3_y - 0.31*cm, "TAG:")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_DARK)
        canvas.drawString(x0 + 1.1*cm, bar3_y - 0.31*cm, tag)

        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(C_BAR)
        canvas.drawString(x0 + 3.2*cm, bar3_y - 0.31*cm, "Equipamento:")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_DARK)
        canvas.drawString(x0 + 5.5*cm, bar3_y - 0.31*cm, tipo)

        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(C_BAR)
        canvas.drawString(x0 + 10.0*cm, bar3_y - 0.31*cm, "Série:")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_DARK)
        canvas.drawString(x0 + 11.2*cm, bar3_y - 0.31*cm, serie)

        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(C_BAR)
        canvas.drawString(x0 + 13.5*cm, bar3_y - 0.31*cm, "Horímetro:")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_DARK)
        canvas.drawString(x0 + 15.0*cm, bar3_y - 0.31*cm, f"{horo:.0f} h")

        # linha separadora abaixo do cabeçalho
        canvas.setStrokeColor(C_LINE)
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

    # ── Paleta light (fundo branco) ───────────────────────────────────────────
    DARK_BLUE  = colors.HexColor("#003366")   # títulos
    MID_BLUE   = colors.HexColor("#005F9E")   # seções
    ACCENT     = colors.HexColor("#0088CC")   # cabeçalho de tabela
    ROW_ALT    = colors.HexColor("#EAF4FB")   # linha alternada tabela
    BLACK      = colors.HexColor("#1A1A1A")   # corpo de texto
    GRAY       = colors.HexColor("#555555")   # caption
    WHITE      = colors.white
    HR_COLOR   = colors.HexColor("#0088CC")

    title_style = ParagraphStyle(
        "APMTitle", parent=styles["Title"],
        fontSize=22, textColor=DARK_BLUE, spaceAfter=2,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "APMSub", parent=styles["Normal"],
        fontSize=11, textColor=MID_BLUE, spaceAfter=6,
    )
    section_style = ParagraphStyle(
        "APMSection", parent=styles["Heading2"],
        fontSize=12, textColor=MID_BLUE,
        spaceBefore=14, spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "APMBody", parent=styles["Normal"],
        fontSize=9, textColor=BLACK, spaceAfter=3,
    )
    caption_style = ParagraphStyle(
        "APMCaption", parent=styles["Normal"],
        fontSize=8, textColor=GRAY, spaceAfter=2,
    )

    def _hr():
        return HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceAfter=6, spaceBefore=2)

    def _tbl(headers, rows, col_widths=None):
        data = [headers] + rows
        tbl  = Table(data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Cabeçalho
            ("BACKGROUND",    (0, 0), (-1, 0),  ACCENT),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  8),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
            ("TOPPADDING",    (0, 0), (-1, 0),  6),
            # Linhas de dados
            ("BACKGROUND",    (0, 1), (-1, -1), WHITE),
            ("TEXTCOLOR",     (0, 1), (-1, -1), BLACK),
            ("FONTSIZE",      (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#AACCDD")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ]))
        return tbl

    story = []

    # ── Introdução — espaço inicial + identificação do ativo ──────────────────
    story.append(Spacer(1, 0.3*cm))

    # Informações do ativo
    story.append(Paragraph("Identificação do Ativo", section_style))
    asset_rows = [
        ["TAG Operacional",  meta.get("tag", "—"),
         "Tipo de Equipamento", meta.get("tipo_equipamento", "—")],
        ["Número de Série",  meta.get("numero_serie", "—"),
         "Data do Estudo",    meta.get("data_estudo", "—")],
        ["Horímetro Atual",  f"{meta.get('horimetro_atual', 0):.0f} h",
         "Gerado em",         datetime.now().strftime("%Y-%m-%d %H:%M")],
    ]
    tbl_asset = Table(asset_rows, colWidths=[3.5*cm, 5*cm, 4*cm, 5*cm])
    tbl_asset.setStyle(TableStyle([
        ("TEXTCOLOR",   (0, 0), (-1, -1), BLACK),
        ("TEXTCOLOR",   (0, 0), (0, -1),  MID_BLUE),
        ("TEXTCOLOR",   (2, 0), (2, -1),  MID_BLUE),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("FONTNAME",    (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",    (2, 0), (2, -1),  "Helvetica-Bold"),
        ("BACKGROUND",  (0, 0), (-1, -1), ROW_ALT),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#AACCDD")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl_asset)
    story.append(Spacer(1, 0.3*cm))

    # ── Saúde & RUL ──────────────────────────────────────────────────────────
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
            ["Confiabilidade Atual R(t₀)", f"{health_pct:.1f}%",
             "Probabilidade de operação no horímetro atual"],
            ["RUL — Vida Residual",        f"+{rul_time:.0f} h",
             "Tempo até confiabilidade condicional < limiar"],
            ["Horizonte de Intervenção",   f"{horizonte:.0f} h",
             "Horímetro estimado para manutenção preventiva"],
            ["IC 80% RUL (Bootstrap)",     f"[{rul_p10:.0f} — {rul_p90:.0f}] h",
             "Incerteza paramétrica (300 reamostragens)"],
        ],
        col_widths=[5*cm, 4*cm, 8.5*cm],
    ))
    story.append(Spacer(1, 0.3*cm))

    # ── Modelos Paramétricos ──────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Análise de Dados de Vida — Modelos Paramétricos", section_style))

    story.append(Paragraph(
        f"Melhor modelo selecionado: <b>{best.get('model_name','—')}</b> "
        f"— AICc = {_fmt(best.get('aicc'))}",
        body_style,
    ))

    param_rows = []
    for p, label in [("beta", "β (forma)"), ("eta", "η (vida car.)"),
                     ("mu", "μ"), ("sigma", "σ"), ("Lambda", "λ"),
                     ("mttf", "MTTF")]:
        v = best.get(p)
        if v is not None:
            param_rows.append([label, _fmt(v, 4)])

    if param_rows:
        story.append(_tbl(
            ["Parâmetro", "Valor"],
            param_rows,
            col_widths=[5*cm, 5*cm],
        ))

    # Ranking
    ranking = fit.get("ranking", [])
    if ranking:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Ranking AICc dos Modelos", body_style))
        rank_rows = [
            [str(i+1), r.get("model",""), _fmt(r.get("aicc")),
             _fmt(r.get("aicc",0) - ranking[0].get("aicc",0))]
            for i, r in enumerate(ranking)
        ]
        story.append(_tbl(
            ["Pos.", "Modelo", "AICc", "ΔAICc"],
            rank_rows,
            col_widths=[1.5*cm, 5*cm, 3.5*cm, 3.5*cm],
        ))
    story.append(Spacer(1, 0.3*cm))

    # ── Crow-AMSAA ────────────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Análise de Degradação — Crow-AMSAA / NHPP", section_style))

    beta_ca  = ca.get("beta", "—")
    lam_ca   = ca.get("lambda", "—")
    regime   = ca.get("regime", "Indeterminado")
    story.append(_tbl(
        ["Parâmetro", "Valor", "Interpretação"],
        [
            ["β (Crow-AMSAA)", _fmt(beta_ca, 4),
             "β > 1: degradação crescente | β < 1: burn-in | β ≈ 1: aleatório"],
            ["λ (taxa de referência)", _fmt(lam_ca, 6), "Intensidade de falha no ponto de referência"],
            ["Regime", str(regime), ""],
        ],
        col_widths=[4.5*cm, 3.5*cm, 9.5*cm],
    ))
    story.append(Spacer(1, 0.3*cm))

    # ── ML ────────────────────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Machine Learning Preditivo", section_style))

    risk_label = ml.get("risk_label", "—")
    risk_prob  = ml.get("risk_probability", None)
    trend_type = ml.get("trend_type", "—")
    slope      = ml.get("slope", None)
    next_fail  = ml.get("next_failure_estimate", None)

    ml_rows = [
        ["Nível de Risco", str(risk_label),
         f"{risk_prob*100:.1f}%" if risk_prob is not None else "—"],
        ["Tipo de Tendência", str(trend_type),
         f"slope = {_fmt(slope, 4)}" if slope is not None else ""],
        ["Próxima Falha Est.", f"{next_fail:.0f} h" if next_fail else "—", ""],
    ]
    story.append(_tbl(
        ["Indicador", "Valor", "Detalhe"],
        ml_rows,
        col_widths=[5*cm, 5*cm, 7.5*cm],
    ))
    story.append(Spacer(1, 0.3*cm))

    # ── Auditoria ─────────────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Auditoria Estatística dos Dados", section_style))

    n_total  = audit.get("n_total", "—")
    n_fail   = audit.get("n_failures", "—")
    n_cens   = audit.get("n_censored", "—")
    cens_pct = audit.get("censoring_pct", None)
    p_ad     = audit.get("p_value_ad", None)
    kolm     = audit.get("kolmogorov_smirnov", None)

    audit_rows = [
        ["Total de registros",     str(n_total)],
        ["Falhas",                 str(n_fail)],
        ["Censuras",               f"{n_cens} ({cens_pct:.1f}%)" if cens_pct is not None else str(n_cens)],
        ["p-valor Anderson-Darling", _fmt(p_ad, 4) if p_ad else "—"],
        ["Estatística K-S",         _fmt(kolm, 4) if kolm else "—"],
    ]
    story.append(_tbl(
        ["Métrica", "Valor"],
        audit_rows,
        col_widths=[7*cm, 5*cm],
    ))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8*cm))
    story.append(_hr())
    story.append(Paragraph(
        f"Gerado automaticamente pelo APM Analytics — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
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
