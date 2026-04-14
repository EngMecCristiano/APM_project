"""
Utilitários de visualização Plotly — fonte única de verdade para temas e gráficos.
Elimina a duplicação de apply_plotly_theme entre app_apm.py e ml_reliability_module.py.
"""
from __future__ import annotations
from frontend.components.ui_helpers import nbr

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Any, Optional

from frontend.styles.theme import PLOTLY_THEME_KWARGS, GAUGE_STEPS

# Paleta global
COLORS = {
    "primary":  "#00d4ff",
    "accent":   "#A487DE",
    "success":  "#10B981",
    "warning":  "#F59E0B",
    "danger":   "#DC2626",
    "info":     "#3B82F6",
    "forecast": "#D946EF",
    "ci":       "rgba(198, 247, 215, 0.12)",
}


def apply_theme(fig: go.Figure) -> go.Figure:
    """Aplica o tema escuro APM a qualquer figura Plotly."""
    fig.update_layout(**PLOTLY_THEME_KWARGS)
    return fig




# ─── Gráficos de Confiabilidade ───────────────────────────────────────────────

def plot_reliability_function(
    t_plot: List[float],
    y_teorico: List[float],
    func: str,
    asset_tag: str,
    model_name: str,
    show_ci: bool = True,
    emp_x: Optional[List[float]] = None,
    emp_y: Optional[List[float]] = None,
) -> go.Figure:
    fig = go.Figure()

    if show_ci and func in ("SF", "CDF"):
        # IC apenas para SF e CDF (probabilidades limitadas a [0,1])
        y = np.array(y_teorico)
        y_up = np.clip(y * 1.10, 0.0, 1.0).tolist()
        y_lo = np.clip(y * 0.90, 0.0, 1.0).tolist()
        fig.add_trace(go.Scatter(x=t_plot, y=y_up, line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=t_plot, y=y_lo,
                                 fill="tonexty", fillcolor=COLORS["ci"],
                                 line=dict(width=0), name="IC 95%"))

    if emp_x:
        fig.add_trace(go.Scatter(x=emp_x, y=emp_y, mode="lines",
                                 line=dict(shape="hv", dash="dot", color="#4D667A"),
                                 name="Empírico (KM/NA)"))

    fig.add_trace(go.Scatter(x=t_plot, y=y_teorico, mode="lines",
                             line=dict(color=COLORS["primary"], width=3),
                             name=f"Ajuste {model_name}"))

    _y_label = {
        "SF":  "R(t) — Probabilidade de Sobrevivência (0–1)",
        "CDF": "F(t) — Probabilidade de Falha Acumulada (0–1)",
        "PDF": "f(t) — Densidade de Probabilidade (1/h)",
        "HF":  "h(t) — Taxa de Falha Instantânea (falhas/h)",
        "CHF": "H(t) — Hazard Acumulado (adimensional, 0–∞)",
    }.get(func, "Y")

    y_range = [0, 1.05] if func in ("SF", "CDF") else None
    fig.update_layout(
        title=f"[{func}] Análise Estocástica — {asset_tag}  ({_y_label} × Tempo h)",
        height=500,
        yaxis=dict(range=y_range),
    )
    return apply_theme(fig)


def plot_rul(
    t_future: List[float],
    r_conditional: List[float],
    rul_time: float,
    asset_tag: str,
    rul_p10: Optional[float] = None,
    rul_p90: Optional[float] = None,
    rul_threshold: float = 0.10,
) -> go.Figure:
    fig = go.Figure()

    # ── IC Bootstrap (faixa vertical) ────────────────────────────────────────
    if rul_p10 is not None and rul_p90 is not None and rul_p10 < rul_p90:
        fig.add_vrect(
            x0=rul_p10, x1=rul_p90,
            fillcolor="rgba(220,38,38,0.10)",
            line=dict(width=0),
            annotation_text=f"IC 80% RUL",
            annotation_position="top left",
            annotation_font=dict(color=COLORS["danger"], size=11),
        )
        # marcadores das bordas
        fig.add_vline(x=rul_p10, line=dict(color=COLORS["danger"], dash="dot", width=1))
        fig.add_vline(x=rul_p90, line=dict(color=COLORS["danger"], dash="dot", width=1))

    # ── Curva principal ───────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=t_future, y=r_conditional,
        name="R(t|T) — Sobrevivência Condicional",
        line=dict(width=3, color=COLORS["accent"]),
    ))

    # ── Linha de limiar e anotação ────────────────────────────────────────────
    fig.add_hline(
        y=rul_threshold,
        line=dict(color="rgba(220,38,38,0.5)", dash="dot", width=1.5),
        annotation_text=f"Limiar {rul_threshold:.0%}",
        annotation_position="right",
        annotation_font=dict(color=COLORS["danger"], size=11),
    )
    fig.add_shape(type="line",
                  x0=rul_time, x1=rul_time, y0=0, y1=rul_threshold,
                  line=dict(color=COLORS["danger"], dash="dash", width=2))
    fig.add_annotation(
        x=rul_time, y=rul_threshold + 0.03,
        text=f"<b>RUL = {rul_time:.0f} h</b>",
        showarrow=True, arrowhead=2,
        font=dict(color=COLORS["danger"], size=13),
        bgcolor="rgba(0,0,0,0.5)",
    )

    fig.update_layout(
        title=f"Confiabilidade Condicional R(t|T) — {asset_tag}  (R(t|T) × Tempo futuro h)",
        height=480,
        yaxis=dict(range=[0, 1.05]),
    )
    return apply_theme(fig)


def plot_crow_amsaa(
    t_acumulado: List[float],
    n_real: List[int],
    n_teorico: List[float],
    asset_tag: str,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t_acumulado, y=n_real,
                             mode="markers", name="Eventos Reais",
                             marker=dict(color=COLORS["primary"], size=7)))
    fig.add_trace(go.Scatter(x=t_acumulado, y=n_teorico,
                             mode="lines", name="Ajuste NHPP (Crow-AMSAA MLE)",
                             line=dict(color=COLORS["danger"], width=2)))
    fig.update_xaxes(type="log")
    fig.update_yaxes(type="log")
    fig.update_layout(
        title=f"Crow-AMSAA NHPP — {asset_tag}  (Nº falhas acum. × Tempo acum. h — escala log)",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    return apply_theme(fig)


# ─── Gráficos ML ─────────────────────────────────────────────────────────────

def plot_trend(
    tbf_series: List[float],
    slope: float,
    trend_type: str,
    r_squared: float,
) -> go.Figure:
    n = len(tbf_series)
    idx = list(range(n))
    mean_idx = (n - 1) / 2
    trend_line = [slope * i + (np.mean(tbf_series) - slope * mean_idx) for i in idx]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=idx, y=tbf_series, mode="lines+markers",
                             name="TBF Histórico",
                             line=dict(color=COLORS["info"], width=2),
                             marker=dict(size=4)))
    fig.add_trace(go.Scatter(x=idx, y=trend_line, mode="lines",
                             name=f"Tendência ({nbr(slope, 2)} h/ciclo)",
                             line=dict(color=COLORS["danger"], width=2, dash="dash")))
    fig.update_layout(
        title=f"{trend_type} | R²={nbr(r_squared, 3)}  (TBF h × Ciclo)",
        height=400,
    )
    return apply_theme(fig)


def plot_forecast(
    tbf_series: List[float],
    future_tbfs: List[float],
    horimetro_atual: float,
) -> go.Figure:
    n = len(tbf_series)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(n)), y=tbf_series,
                             mode="lines+markers", name="Histórico",
                             line=dict(color=COLORS["info"], width=2),
                             marker=dict(size=4)))
    if future_tbfs:
        fut_x = list(range(n - 1, n + len(future_tbfs)))
        fut_y = [tbf_series[-1]] + future_tbfs
        fig.add_trace(go.Scatter(x=fut_x, y=fut_y,
                                 mode="lines+markers", name="Forecast ML",
                                 line=dict(color=COLORS["forecast"], width=2, dash="dot"),
                                 marker=dict(size=8, symbol="diamond")))
        mean_f = float(np.mean(future_tbfs))
        fig.add_hline(y=mean_f, line_dash="dash", line_color=COLORS["warning"],
                      annotation_text=f"Média prevista: {mean_f:.0f}h")
    fig.update_layout(
        title=f"Forecast Multi-Passo ({len(future_tbfs)} ciclos) — Horímetro: {horimetro_atual:.0f}h  (TBF h × Ciclo)",
        height=400,
    )
    return apply_theme(fig)


def plot_anomalies(
    tbf_series: List[float],
    anomaly_mask: List[bool],
    scores: List[float],
) -> go.Figure:
    n   = len(tbf_series)
    idx = list(range(n))
    normal  = [i for i in idx if not anomaly_mask[i]]
    anomaly = [i for i in idx if anomaly_mask[i]]

    fig = make_subplots(rows=2, cols=1,
                        subplot_titles=("TBF com Anomalias", "Score Isolation Forest"),
                        vertical_spacing=0.22, row_heights=[0.6, 0.4])

    fig.add_trace(go.Scatter(x=normal, y=[tbf_series[i] for i in normal],
                             mode="lines+markers", name="Normal",
                             line=dict(color=COLORS["success"], width=2),
                             marker=dict(size=4)), row=1, col=1)

    if anomaly:
        fig.add_trace(go.Scatter(x=anomaly, y=[tbf_series[i] for i in anomaly],
                                 mode="markers", name="Anomalia",
                                 marker=dict(size=12, color=COLORS["danger"],
                                             symbol="x", line=dict(width=2))), row=1, col=1)

    fig.add_trace(go.Scatter(x=idx, y=scores, mode="lines", name="Score IF",
                             line=dict(color="#8B5CF6", width=2),
                             fill="tozeroy", fillcolor="rgba(139,92,246,0.12)"), row=2, col=1)

    fig.update_layout(
        title="Detecção de Anomalias — Isolation Forest  (TBF h e Score × Ciclo)",
        height=520,
    )
    return apply_theme(fig)


def plot_feature_importance(features: List[str], importances: List[float]) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=importances, y=features, orientation="h",
        marker=dict(color=importances, colorscale="Blues", showscale=False),
    ))
    fig.update_layout(
        title="Importância das Features — Random Forest  (Importância Gini × Feature)",
        height=max(300, len(features) * 28),
        margin=dict(l=140),
    )
    return apply_theme(fig)


def plot_risk_gauge(score: int, color: str, classification: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"Score de Risco<br><span style='font-size:0.85em'>{classification}</span>"},
        delta={"reference": 50,
               "increasing": {"color": COLORS["danger"]},
               "decreasing": {"color": COLORS["success"]}},
        gauge={
            "axis":      {"range": [0, 100], "tickcolor": "#374151"},
            "bar":       {"color": color},
            "steps":     GAUGE_STEPS,
            "threshold": {"line": {"color": "#F0FFFF", "width": 3},
                          "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(height=300, margin=dict(t=60, b=20),
                      paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#F0FFFF"))
    return fig


def plot_pmo_curve(pmo: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pmo["t_range"], y=pmo["custo_curva"],
        mode="lines", name="Taxa de Custo C(tp)",
        line=dict(color="#4F46E5", width=3),
    ))
    fig.add_vline(x=pmo["tp_otimo"],
                  line_dash="dash", line_color=COLORS["danger"], line_width=2,
                  annotation_text=f"tp* = {pmo['tp_otimo']:.0f}h",
                  annotation_position="top right")
    fig.add_trace(go.Scatter(
        x=[pmo["tp_otimo"]], y=[pmo["custo_na_otimo"]],
        mode="markers", name=f"Ótimo ({pmo['tp_otimo']:.0f}h)",
        marker=dict(size=14, color=COLORS["danger"], symbol="star"),
    ))
    fig.add_hline(y=pmo["custo_corretivo_puro"],
                  line_dash="dot", line_color="#6B7280",
                  annotation_text="Política Corretiva Pura",
                  annotation_position="bottom right")
    fig.update_layout(
        title="Otimização PMO — Teoria da Renovação  (Custo/hora × Intervalo tp h)",
        height=420,
    )
    return apply_theme(fig)


def plot_qq(
    qq_theoretical: List[float],
    qq_observed: List[float],
    model_name: str,
) -> go.Figure:
    """QQ Plot correto — quantis observados vs. quantis teóricos da distribuição ajustada."""
    all_vals = qq_theoretical + qq_observed
    lim = [min(all_vals) * 0.95, max(all_vals) * 1.05]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=qq_theoretical, y=qq_observed,
                             mode="markers", name="Dados Observados",
                             marker=dict(color=COLORS["primary"], size=8, opacity=0.75)))
    fig.add_trace(go.Scatter(x=lim, y=lim, mode="lines",
                             name="Referência (y=x)",
                             line=dict(color=COLORS["danger"], dash="dash")))
    fig.update_layout(
        title=f"QQ Plot — Quantis {model_name} vs. Observados  (Observados × Teóricos {model_name})",
        height=420,
    )
    return apply_theme(fig)


def plot_tbf_histogram(tbf_values: List[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=tbf_values, nbinsx=30,
                               name="TBF", marker_color=COLORS["primary"], opacity=0.75))
    mean_v = float(np.mean(tbf_values))
    fig.add_vline(x=mean_v, line_dash="dash", line_color=COLORS["danger"],
                  annotation_text=f"Média: {nbr(mean_v, 1)}h")
    fig.update_layout(
        title="Distribuição dos Tempos Entre Falhas (TBF)  (Frequência × TBF h)",
        height=400,
    )
    return apply_theme(fig)


def plot_boxplot(tbf_fail: List[float], tbf_cens: List[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(y=tbf_fail, name="Falhas",
                         marker_color=COLORS["danger"], boxmean="sd"))
    fig.add_trace(go.Box(y=tbf_cens, name="Censuras",
                         marker_color=COLORS["success"], boxmean="sd"))
    fig.update_layout(
        title="Comparação TBF: Falhas vs. Censuras  (TBF h × Grupo)",
        height=400,
    )
    return apply_theme(fig)
