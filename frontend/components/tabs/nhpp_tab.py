"""
Aba NHPP — Análise de Degradação Crow-AMSAA (RGA).
"""
from __future__ import annotations

import streamlit as st
from typing import Dict, Any

from frontend.components.charts import plot_crow_amsaa
from frontend.components.ui_helpers import nbr, kpi_row
from frontend.styles.theme import PLOTLY_CONFIG


def render(ca: Dict[str, Any], meta: Dict[str, Any]) -> None:
    beta = ca["beta"]

    with st.expander("ℹ️ Como interpretar esta aba — Degradação RGA/NHPP (Crow-AMSAA)", expanded=False):
        st.markdown("""
**O que é Crow-AMSAA?**
Modelo de processo não-homogêneo de Poisson (NHPP) que analisa se o equipamento está piorando,
estável ou melhorando ao longo do tempo — independente da distribuição de cada falha individual.

**Como ler o gráfico:**
- Eixo X: tempo acumulado de operação (escala log)
- Eixo Y: número acumulado de falhas (escala log)
- **Pontos azuis:** falhas reais observadas
- **Linha vermelha:** ajuste do modelo NHPP (Crow-AMSAA MLE)

Uma linha reta no gráfico log-log indica processo estacionário (HPP).
Curvatura para cima = degradação. Curvatura para baixo = melhoria.

**Como ler o parâmetro β:**

| β | Regime | O que fazer |
|---|---|---|
| **β > 1** | Taxa de falha crescente — equipamento degradando | Planejar substituição preventiva por idade |
| **β ≈ 1** | Taxa de falha constante — processo aleatório (HPP) | Manutenção corretiva ou inspeção periódica |
| **β < 1** | Taxa de falha decrescente — melhoria ou mortalidade infantil | Investigar causa-raiz das primeiras falhas |

**λ (lambda):** intensidade base do processo. Quanto maior, mais frequentes as falhas por unidade de tempo.
        """)

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
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

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
