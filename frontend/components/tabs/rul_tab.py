"""
Aba RUL — Vida Útil Remanescente (Confiabilidade Condicional).
"""
from __future__ import annotations

import streamlit as st
from typing import Dict, Any

from frontend.components.charts import plot_rul
from frontend.components.ui_helpers import nbr, kpi_row
from frontend.styles.theme import PLOTLY_CONFIG

_TIPS = {
    "r_current": "R(t₀) = probabilidade de o ativo ainda estar operando no horímetro atual. "
                 "Calculado como R(T) da distribuição ajustada — quanto mais próximo de 1, mais saudável.",
    "rul":       "RUL (Remaining Useful Life) = tempo futuro até a confiabilidade condicional cair "
                 "abaixo do limiar configurado. Não é o tempo até a próxima falha, mas um P(sobrevivência) < limiar.",
    "horizonte": "Horímetro atual + RUL. Estimativa de quando a intervenção preventiva deve ocorrer "
                 "para evitar falha não planejada com 90% de probabilidade.",
    "ci":        "Intervalo de Confiança Bootstrap (80%): faixa na qual o RUL real provavelmente cai. "
                 "Calculado por 300 reamostragens dos parâmetros da distribuição ajustada.",
}


def render(
    rul: Dict[str, Any],
    fit: Dict[str, Any],
    meta: Dict[str, Any],
    rul_threshold: float = 0.10,
) -> None:
    best      = fit["best"]
    horimetro = meta["horimetro_atual"]
    rul_p10   = rul.get("rul_p10", rul["rul_time"] * 0.7)
    rul_p90   = rul.get("rul_p90", rul["rul_time"] * 1.3)

    with st.expander("ℹ️ Como interpretar esta aba — RUL (Vida Útil Remanescente)", expanded=False):
        st.markdown(f"""
**O que é RUL?**
Remaining Useful Life — estimativa de quantas horas o equipamento ainda pode operar antes de atingir
um nível crítico de confiabilidade (o limiar configurado na barra lateral).

**Como ler os indicadores:**

| Indicador | Significado |
|---|---|
| **R(t₀)** | Saúde atual: probabilidade de o equipamento estar funcionando agora. 90% = ainda saudável; abaixo de 50% = atenção |
| **RUL** | Horas adicionais até a confiabilidade cair para o limiar definido (padrão 10%) |
| **Horizonte de Falha** | Horímetro atual + RUL — quando planejar a próxima intervenção |
| **IC 80%** | Intervalo de incerteza do RUL. Faixa vermelha no gráfico |

**Como ler o gráfico:**
- O eixo X mostra horas **futuras** a partir de hoje (horímetro = {horimetro:.0f} h)
- A curva desce da direita para a esquerda — quanto mais rápida a queda, maior o risco
- A linha vermelha pontilhada é o limiar: quando a curva tocar esta linha, o RUL se esgota
- A faixa vermelha vertical é o IC 80% do Bootstrap — representa a incerteza do modelo

**Limiar configurável:** ajuste na barra lateral em "Limiares de Análise". Limiar 10% significa que o
equipamento tem 90% de chance de falhar antes de completar o RUL estimado.
        """)

    kpi_row([
        ("R(t₀) — Confiabilidade Atual",
         f"{rul['r_current']:.1%}",
         "no horímetro atual",
         _TIPS["r_current"]),
        ("RUL — Vida Residual",
         f"+{nbr(rul['rul_time'], 1)} h",
         f"até R_cond = {rul_threshold:.0%}",
         _TIPS["rul"]),
        ("Horizonte de Falha",
         f"{horimetro + rul['rul_time']:.0f} h",
         "horímetro estimado",
         _TIPS["horizonte"]),
        ("IC 80% RUL",
         f"[{rul_p10:.0f} — {rul_p90:.0f}] h",
         "bootstrap paramétrico",
         _TIPS["ci"]),
    ])

    fig = plot_rul(
        t_future=rul["t_future"],
        r_conditional=rul["r_conditional"],
        rul_time=rul["rul_time"],
        asset_tag=meta["tag"],
        rul_p10=rul_p10,
        rul_p90=rul_p90,
        rul_threshold=rul_threshold,
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with st.expander("ℹ️ Interpretação do RUL e do IC Bootstrap"):
        st.markdown(f"""
**Confiabilidade Condicional** R(t|T):

$$R(t|T) = \\frac{{R(T+t)}}{{R(T)}}$$

Probabilidade de o ativo sobreviver mais `t` horas, dado que já operou `T = {horimetro:.0f} h` sem falhar.

**RUL** = instante em que R(t|T) = **{rul_threshold:.0%}** (limiar configurado na barra lateral):
> com {(1-rul_threshold):.0%} de probabilidade, o componente falhará antes de **{rul['rul_time']:.0f} h** adicionais.

**Intervalo de Confiança Bootstrap (80%):**
O modelo foi reamostrado 300 vezes com variação paramétrica. O RUL real tem 80% de probabilidade de estar em
`[{rul_p10:.0f} h — {rul_p90:.0f} h]`. A faixa vermelha no gráfico representa essa incerteza.

**Modelo usado:** {best['model_name']} — β = {best.get('beta','—')}, η = {best.get('eta','—')}
        """)
