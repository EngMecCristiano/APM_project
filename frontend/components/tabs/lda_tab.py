"""
Aba LDA — Life Data Analysis.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from typing import Dict, Any, List

from frontend.components.charts import plot_reliability_function
from frontend.components.ui_helpers import nbr, kpi_row, html_table

# Tooltips explicativos por KPI
_TIPS = {
    "beta":    "Parâmetro de forma da Weibull. β > 1 = desgaste (falha por envelhecimento); β = 1 = aleatório; β < 1 = mortalidade infantil.",
    "eta":     "Vida característica: 63,2% dos equipamentos terão falhado até este horímetro. Equivale ao percentil 63,2% da distribuição.",
    "mu":      "Logaritmo natural da mediana do tempo de falha. Ex: μ = 6,5 → mediana ≈ 665 h.",
    "sigma":   "Dispersão da distribuição em escala logarítmica. Valores altos indicam alta variabilidade entre falhas.",
    "lam":     "Taxa de falha constante (processos aleatórios). MTBF = 1/λ. Indicativo de processo de Poisson (HPP).",
    "mttf":    "Mean Time To Failure — tempo médio esperado até a falha, calculado como ∫₀^∞ R(t) dt.",
    "aicc":    "Critério de Akaike Corrigido — penaliza modelos com muitos parâmetros. |ΔAICc| > 4 indica diferença significativa entre modelos.",
}


def render(records: List[Dict], fit: Dict[str, Any], meta: Dict[str, Any]) -> None:
    best    = fit["best"]
    ranking = fit["ranking"]
    delta   = fit.get("delta_aicc", 0.0)

    col_f, col_ci = st.columns([3, 1])
    with col_f:
        func = st.selectbox("Função de Confiabilidade", ["SF", "PDF", "CDF", "HF", "CHF"],
                            help="SF = Sobrevivência | PDF = Densidade | CDF = Acumulada | HF = Taxa de Falha | CHF = Hazard Acumulado")
    with col_ci:
        show_ci = st.checkbox("IC 95%", value=True, help="Faixa de incerteza aproximada ±10% ao redor da curva teórica")

    tbf_vals  = [r["TBF"] for r in records]
    tbf_fail  = [r["TBF"] for r in records if r["Falha"] == 1]
    tbf_cens  = [r["TBF"] for r in records if r["Falha"] == 0]
    t_max     = max(tbf_vals) if tbf_vals else 1000
    t_plot    = np.linspace(0.01 if func in ("SF", "CDF", "CHF") else 2.0, t_max * 1.5, 300).tolist()
    y_vals    = _eval_distribution(func, t_plot, best)

    # ── Kaplan-Meier empírico (apenas SF) ────────────────────────────────────
    emp_x, emp_y = None, None
    if func == "SF" and len(tbf_fail) >= 3:
        emp_x, emp_y = _kaplan_meier(tbf_fail, tbf_cens)

    fig = plot_reliability_function(
        t_plot=t_plot, y_teorico=y_vals,
        func=func, asset_tag=meta["tag"],
        model_name=best["model_name"],
        show_ci=show_ci,
        emp_x=emp_x, emp_y=emp_y,
    )
    st.plotly_chart(fig, width="stretch")

    if emp_x is not None:
        st.caption("Linha tracejada = estimativa empírica Kaplan-Meier (não paramétrica). "
                   "Quanto mais próxima do modelo, melhor o ajuste.")

    # ── Ranking de modelos ────────────────────────────────────────────────────
    st.markdown("#### Ranking de Modelos — AICc")
    df_rank = pd.DataFrame([
        {"Pos.": i + 1, "Modelo": r["model"], "AICc": f"{nbr(r['aicc'], 2)}",
         "ΔAICc": f"{nbr(r['aicc'] - ranking[0]['aicc'], 2)}"}
        for i, r in enumerate(ranking)
    ])
    html_table(df_rank)

    if abs(delta) > 4:
        st.success(f"✅ **{best['model_name']}** significativamente melhor (|ΔAICc| = {nbr(abs(delta), 1)} > 4)",
                   icon="✅")
    elif abs(delta) > 2:
        st.info(f"ℹ️ **{best['model_name']}** tem suporte moderado (|ΔAICc| = {nbr(abs(delta), 1)})")
    else:
        st.warning("⚠️ Modelos com suporte similar — use conhecimento de domínio para escolher")

    with st.expander(f"📐 Parâmetros — {best['model_name']}", expanded=True):
        _show_params(best)


def _kaplan_meier(tbf_fail: list, tbf_cens: list) -> tuple:
    """Estimativa Kaplan-Meier via biblioteca reliability."""
    try:
        from reliability.Nonparametric import KaplanMeier
        km = KaplanMeier(
            failures=tbf_fail,
            right_censored=tbf_cens if tbf_cens else None,
            show_plot=False, print_results=False,
        )
        return list(km.xvals), list(km.KM)
    except Exception:
        return None, None


def _eval_distribution(func: str, t_plot: list, params: Dict) -> list:
    from scipy.stats import weibull_min, lognorm, norm, expon
    t  = np.array(t_plot)
    dt = params["dist_type"]
    if dt == "weibull":
        dist = weibull_min(params["beta"], scale=params["eta"])
    elif dt == "lognormal":
        dist = lognorm(s=params["sigma"], scale=np.exp(params["mu"]))
    elif dt == "normal":
        dist = norm(loc=params["mu"], scale=params["sigma"])
    elif dt == "exponential":
        dist = expon(scale=1.0 / params["lam"])
    else:
        return [0.0] * len(t_plot)
    fn = {"SF": dist.sf, "PDF": dist.pdf, "CDF": dist.cdf,
          "HF": lambda x: dist.pdf(x) / np.maximum(dist.sf(x), 1e-15),
          "CHF": lambda x: -np.log(np.maximum(dist.sf(x), 1e-15))}
    return fn[func](t).tolist()


def _show_params(p: Dict) -> None:
    dt = p["dist_type"]
    if dt == "weibull":
        st.latex(r"f(t)=\frac{\beta}{\eta}\left(\frac{t}{\eta}\right)^{\beta-1}e^{-(t/\eta)^\beta}")
        regime = ("Desgaste — falha por envelhecimento (β > 1)" if p["beta"] > 1
                  else "Mortalidade Infantil — falha por defeito precoce (β < 1)" if p["beta"] < 1
                  else "Aleatório — taxa de falha constante (β = 1)")
        kpi_row([
            ("β — Forma",  f"{nbr(p['beta'], 4)}", regime,         _TIPS["beta"]),
            ("η — Escala", f"{nbr(p['eta'], 1)} h", "Vida característica (P63.2)", _TIPS["eta"]),
            ("MTBF",       f"{nbr(p['mttf'], 1)} h", "Esperança de vida",          _TIPS["mttf"]),
        ])
    elif dt == "lognormal":
        st.latex(r"f(t)=\frac{1}{t\sigma\sqrt{2\pi}}e^{-(\ln t-\mu)^2/(2\sigma^2)}")
        kpi_row([
            ("μ — Log-média",  f"{nbr(p['mu'], 4)}",   "Localização em log-escala",  _TIPS["mu"]),
            ("σ — Log-desvio", f"{nbr(p['sigma'], 4)}", "Dispersão em log-escala",    _TIPS["sigma"]),
            ("MTBF",           f"{nbr(p['mttf'], 1)} h", "Esperança de vida",         _TIPS["mttf"]),
        ])
    elif dt == "normal":
        st.latex(r"f(t)=\frac{1}{\sigma\sqrt{2\pi}}e^{-(t-\mu)^2/(2\sigma^2)}")
        kpi_row([
            ("μ — Média",  f"{nbr(p['mu'], 1)} h",   "Centro da distribuição",   _TIPS["mttf"]),
            ("σ — Desvio", f"{nbr(p['sigma'], 1)} h", "Dispersão dos TBFs",       _TIPS["sigma"]),
            ("MTBF",       f"{nbr(p['mttf'], 1)} h",  "Esperança de vida",        _TIPS["mttf"]),
        ])
    elif dt == "exponential":
        st.latex(r"f(t)=\lambda e^{-\lambda t}")
        kpi_row([
            ("λ — Taxa de Falha", f"{nbr(p['lam'], 6)}", "falhas/h",          _TIPS["lam"]),
            ("MTBF",              f"{nbr(p['mttf'], 1)} h", "= 1/λ",          _TIPS["mttf"]),
            ("Regime",            "Aleatório", "Processo HPP (β = 1)",    _TIPS["beta"]),
        ])
