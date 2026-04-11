"""
Aba NHPP — Análise de Degradação Crow-AMSAA (RGA).
"""
from __future__ import annotations

import streamlit as st
from typing import Dict, Any

from frontend.components.charts import plot_crow_amsaa
from frontend.components.ui_helpers import nbr, kpi_row


def render(ca: Dict[str, Any], meta: Dict[str, Any]) -> None:
    beta = ca["beta"]

    if beta > 1.05:
        color, regime = "#E73617", "Degradação ↑"
    elif beta < 0.95:
        color, regime = "#03FC9F", "Melhoria ↓"
    else:
        color, regime = "#DFB017", "Estacionário ≈"

    kpi_row([
        ("β — Parâmetro de Forma",  f"{nbr(beta, 4)}",          regime),
        ("λ — Parâmetro de Escala", f"{nbr(ca['lam'], 6)}",     "Intensidade base"),
        ("Processo",                ca["interpretation"][:30] + ("…" if len(ca["interpretation"]) > 30 else ""),
                                    "Crow-AMSAA (MLE)"),
    ])

    fig = plot_crow_amsaa(
        t_acumulado=ca["t_acumulado"],
        n_real=ca["n_real"],
        n_teorico=ca["n_teorico"],
        asset_tag=meta["tag"],
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown(f"""
<div class="beta-box" style="border-left-color:{color};">
  <span style="color:{color};font-size:17px;">β = {nbr(beta, 4)} &nbsp;|&nbsp; λ = {nbr(ca['lam'], 6)}</span>
  <br/><span style="font-size:14px;font-weight:400;">{ca['interpretation']}</span>
</div>
""", unsafe_allow_html=True)

    with st.expander("📐 Estimadores MLE — Crow-AMSAA"):
        st.markdown(r"""
**Estimador MLE (não viesado):**

$$\hat{\beta} = \frac{n}{n \cdot \ln(T_{max}) - \sum_{i=1}^{n} \ln(T_i)}
\qquad
\hat{\lambda} = \frac{n}{T_{max}^{\hat{\beta}}}$$

| β | Regime | Ação recomendada |
|---|---|---|
| β > 1 | Desgaste — taxa crescente | Substituição preventiva por idade |
| β ≈ 1 | Estacionário (HPP) | Corretiva ou inspeção periódica |
| β < 1 | Melhoria / mortalidade infantil | Investigar causa-raiz |
        """)
