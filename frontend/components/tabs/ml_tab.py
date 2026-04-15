"""
Aba ML — Machine Learning Prescritivo.
Predição TBF + Detecção de Anomalias + Score de Risco + PMO.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Dict, Any, List

import frontend.api_client as api
from frontend.components.charts import (
    plot_trend, plot_forecast, plot_anomalies,
    plot_feature_importance, plot_risk_gauge, plot_pmo_curve,
)
from frontend.components.ui_helpers import nbr, kpi_row, html_table
from frontend.styles.theme import PLOTLY_CONFIG


def render(
    ml: Dict[str, Any],
    fit: Dict[str, Any],
    rul: Dict[str, Any],
    records: List[Dict],
    meta: Dict[str, Any],
) -> None:
    trend     = ml["trend"]
    anomalies = ml["anomalies"]
    metrics   = ml["metrics"]
    forecast  = ml["forecast"]
    risk      = ml["risk"]
    feat_imp  = ml.get("feature_importance")
    best      = fit["best"]

    tbf_series = [r["TBF"] for r in records]

    # ── KPIs de cabeçalho (compactos via HTML para evitar overflow) ──────────
    trend_short = (trend["trend_type"][:18] + "…") if len(trend["trend_type"]) > 18 else trend["trend_type"]
    kpi_items = [
        ("Score de Risco",    f"{risk['score']}/100",  risk["classification"]),
        ("Tendência",         trend_short,              f"{nbr(trend['degradation_rate'], 2)}%/ciclo"),
        ("Anomalias",         str(anomalies["count"]),  f"{nbr(anomalies['count'] / max(len(records),1) * 100, 1)}% dos dados"),
        ("Próximo TBF (ML)",  f"{forecast['next_tbf']:.0f}h" if forecast["next_tbf"] else "N/A", "Random Forest"),
        ("Modelo R²",         f"{nbr(metrics['r2'], 3)}" if metrics["samples"] > 0 else "N/A",
                              f"MAE {nbr(metrics['mae'], 1)}h"),
    ]
    cols = st.columns(5)
    for col, (label, val, sub) in zip(cols, kpi_items):
        col.markdown(f"""
        <div style="background:rgba(0,212,255,0.06);border:1px solid rgba(0,212,255,0.15);
                    border-radius:10px;padding:8px 10px;text-align:center;">
            <div style="font-size:10px;color:#90C8E0;letter-spacing:.8px;text-transform:uppercase;
                        margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {label}</div>
            <div style="font-size:18px;font-weight:700;color:#63DCF7;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{val}</div>
            <div style="font-size:10px;color:#A8CEDD;margin-top:2px;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{sub}</div>
        </div>""", unsafe_allow_html=True)

    with st.expander("ℹ️ Como interpretar esta aba — Machine Learning Prescritivo", expanded=False):
        st.markdown("""
**O que esta aba faz?**
Combina o modelo paramétrico de confiabilidade com algoritmos de Machine Learning para gerar
diagnóstico em tempo real e prescrições de manutenção acionáveis.

| Sub-aba | O que analisa |
|---|---|
| **Predição & Tendência** | Tendência histórica dos TBFs e previsão dos próximos ciclos via Random Forest |
| **Detecção de Anomalias** | Identifica TBFs anômalos (falhas precoces ou outliers) via Isolation Forest |
| **Score de Risco** | Pontuação 0–100 combinando confiabilidade, tendência e anomalias |
| **Otimização PMO** | Intervalo ótimo de manutenção preventiva pela Teoria da Renovação |

**Score de Risco:**
- 0–29 → Baixo (verde) — operação normal
- 30–49 → Médio (amarelo) — monitorar
- 50–69 → Alto (laranja) — planejar intervenção
- 70–100 → Crítico (vermelho) — agir imediatamente
        """)

    st.divider()

    # ── Abas ML internas ──────────────────────────────────────────────────────
    tab_pred, tab_anom, tab_risk, tab_pmo = st.tabs([
        "📈 Predição & Tendência",
        "🔍 Detecção de Anomalias",
        "⚠️ Score de Risco",
        "🔧 Otimização PMO",
    ])

    with tab_pred:
        _render_prediction(trend, forecast, feat_imp, tbf_series, metrics, meta)

    with tab_anom:
        _render_anomalies(anomalies, tbf_series)

    with tab_risk:
        _render_risk(risk, rul, forecast, meta, best)

    with tab_pmo:
        _render_pmo(best, meta)


# ─── Sub-renderizadores ───────────────────────────────────────────────────────

def _render_prediction(trend, forecast, feat_imp, tbf_series, metrics, meta):
    with st.expander("ℹ️ Como interpretar — Predição & Tendência", expanded=False):
        st.markdown("""
**Gráfico de Tendência (linha azul):**
Mostra a evolução histórica dos TBFs. A linha tracejada vermelha é a regressão linear.
- Inclinação negativa (descendo) → TBFs diminuindo → equipamento degradando
- Inclinação positiva (subindo) → TBFs aumentando → equipamento melhorando ou regime pós-infant mortality

**R² (coeficiente de determinação):** quanto da variação dos TBFs é explicada pela tendência.
R² próximo de 1 = tendência forte; próximo de 0 = variação aleatória.

**Importância das Features (gráfico de barras):**
Mostra quais variáveis o Random Forest usou mais para prever o próximo TBF.
Features com maior barra = mais influentes na predição.

**Forecast (gráfico de previsão):**
Os próximos ciclos previstos pelo Random Forest (pontos diamante roxos).
A linha amarela tracejada indica a média esperada dos próximos TBFs.
Use para antecipar se o próximo TBF será curto (risco) ou longo (seguro).

**Métricas do modelo:**
- **R²**: qualidade do ajuste (>0.7 = bom; <0.4 = modelo com limitações)
- **MAE**: erro médio absoluto em horas — margem de erro esperada nas previsões
        """)

    col_a, col_b = st.columns([3, 2])

    with col_a:
        fig_trend = plot_trend(
            tbf_series=tbf_series,
            slope=trend["slope"],
            trend_type=trend["trend_type"],
            r_squared=trend["r_squared"],
        )
        st.plotly_chart(fig_trend, use_container_width=True, config=PLOTLY_CONFIG)

        if trend["slope"] < 0:
            st.warning(
                f"⚠️ **{trend['trend_type']}** — TBF decrescendo "
                f"{nbr(abs(trend['slope']), 2)} h/ciclo "
                f"(p={nbr(trend['p_value'], 3)}, R²={nbr(trend['r_squared'], 3)}). "
                "Revisar plano de manutenção preventiva."
            )
        else:
            st.success(
                f"✅ **{trend['trend_type']}** — Equipamento estável. "
                f"(R²={nbr(trend['r_squared'], 3)})"
            )

    with col_b:
        if feat_imp and len(feat_imp["features"]) > 0:
            st.plotly_chart(
                plot_feature_importance(feat_imp["features"], feat_imp["importances"]),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )
        else:
            st.info("Importância de features indisponível.")

    st.markdown(f"#### Forecast — {len(forecast['future_tbfs'])} Ciclos à Frente")

    if forecast["future_tbfs"]:
        st.plotly_chart(
            plot_forecast(tbf_series, forecast["future_tbfs"], meta["horimetro_atual"]),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
        df_fc = pd.DataFrame({
            "Ciclo": [f"t+{i+1}" for i in range(len(forecast["future_tbfs"]))],
            "TBF Previsto (h)": [f"{v:.0f}" for v in forecast["future_tbfs"]],
        })
        html_table(df_fc)
    else:
        st.warning("Forecast indisponível — dados insuficientes.")

    if metrics["samples"] > 0:
        with st.expander("Métricas do Modelo Random Forest"):
            kpi_row([
                ("R²",       f"{nbr(metrics['r2'], 4)}", "ajuste do modelo"),
                ("MAE (h)",  f"{nbr(metrics['mae'], 1)}", "erro absoluto médio"),
                ("RMSE (h)", f"{nbr(metrics['rmse'], 1)}", "raiz do erro quadrático"),
            ])


def _render_anomalies(anomalies, tbf_series):
    with st.expander("ℹ️ Como interpretar — Detecção de Anomalias", expanded=False):
        st.markdown("""
**Algoritmo:** Isolation Forest — detecta TBFs que fogem do padrão histórico.

**Gráfico superior (TBF histórico):**
- Pontos verdes = TBFs normais
- X vermelho = TBF anômalo detectado

**Gráfico inferior (Score Isolation Forest):**
Scores mais negativos = mais anômalo. Picos para baixo indicam os eventos mais incomuns.

**Como interpretar os tipos de anomalia:**

| Tipo | Indicativo | O que investigar |
|---|---|---|
| TBF muito curto (↘) | Falha precoce, mortalidade infantil | Erro de montagem, sobrecarga, lote defeituoso |
| TBF muito longo (↗) | Censura não registrada, manutenção de oportunidade | Verificar se o equipamento realmente operou todo esse tempo |

**Contaminação configurada:** 10% — o modelo espera que ~10% dos dados sejam anômalos.
Se o equipamento for muito estável, pode haver falsos positivos.
        """)

    st.plotly_chart(
        plot_anomalies(tbf_series, anomalies["anomaly_mask"], anomalies["scores"]),
        use_container_width=True,
        config=PLOTLY_CONFIG,
    )
    if anomalies["count"] > 0:
        st.info(
            f"🔍 **{anomalies['count']} anomalia(s) detectada(s)** — "
            f"{nbr(anomalies['count'] / len(tbf_series) * 100, 1)}% do histórico"
        )
        import numpy as np
        mean_tbf = float(np.mean(tbf_series))
        rows = []
        for idx, val in zip(anomalies["indices"], anomalies["values"]):
            rows.append({
                "Ciclo": idx,
                "TBF Anômalo (h)": f"{val:.0f}",
                "Desvio da Média (%)": f"{nbr((val - mean_tbf) / mean_tbf * 100, 1)}%",
                "Classificação": (
                    "↘ TBF Curto (falha precoce)" if val < mean_tbf * 0.6
                    else "↗ TBF Longo (possível censura)"
                ),
            })
        html_table(pd.DataFrame(rows))
        st.markdown("""
**Causas típicas em mineração:**
- **TBF curto**: mortalidade infantil, erro de montagem, sobrecarga pontual
- **TBF longo**: possível censura não registrada ou manutenção de oportunidade
        """)
    else:
        st.success("✅ Nenhuma anomalia detectada no histórico de TBF.")


def _render_risk(risk, rul, forecast, meta, best):
    with st.expander("ℹ️ Como interpretar — Score de Risco", expanded=False):
        st.markdown("""
**O Score de Risco (0–100)** combina quatro componentes em uma única pontuação de saúde do ativo:

| Componente | Peso máx. | O que avalia |
|---|---|---|
| Confiabilidade R(t) | 30 pts | Quanto da vida útil já foi consumida |
| Tendência TBF | 30 pts | Se os TBFs estão diminuindo ao longo do tempo |
| Anomalias (Isolation Forest) | 25 pts | Frequência e intensidade de eventos anômalos |
| Proximidade TBF ML | 15 pts | Se o próximo TBF previsto é menor que a média histórica |

**Escala de risco:**
- **0–29** (verde) → Baixo — operação normal, monitorar normalmente
- **30–49** (amarelo) → Médio — aumentar frequência de inspeção
- **50–69** (laranja) → Alto — planejar intervenção nas próximas semanas
- **70–100** (vermelho) → Crítico — agir imediatamente

**Barras de decomposição:** mostram quanto cada componente contribuiu para o score total.
Barras vermelhas indicam o componente que mais está elevando o risco — foque a investigação aí.
        """)

    col_g, col_d = st.columns([2, 3])

    with col_g:
        st.plotly_chart(
            plot_risk_gauge(risk["score"], risk["color"], risk["classification"]),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
        st.markdown(f"""
<div style="background:{risk['color']}22; border-left:4px solid {risk['color']};
            padding:12px; border-radius:4px; margin-top:8px;">
<b>{risk['classification']}</b><br/>{risk['urgency']}<br/><br/>
<i>📋 {risk['action']}</i>
</div>""", unsafe_allow_html=True)

    with col_d:
        st.subheader("Decomposição do Score")
        comps = risk["components"]
        limits = {"tendency_tbf": 30, "anomalies_if": 25,
                  "reliability_rt": 30, "proximity_ml": 15}
        labels = {"tendency_tbf": "Tendência TBF",
                  "anomalies_if": "Anomalias (IF)",
                  "reliability_rt": "Confiabilidade R(t)",
                  "proximity_ml": "Proximidade TBF ML"}
        for key, lim in limits.items():
            val = comps[key]
            pct = val / lim
            bar_color = "#DC2626" if pct > 0.7 else "#F59E0B" if pct > 0.4 else "#10B981"
            st.markdown(f"**{labels[key]}** — {val}/{lim} pts")
            st.progress(pct)

        st.divider()
        info = {
            "TAG":                   meta["tag"],
            "Horímetro (h)":        f"{meta['horimetro_atual']:.0f}",
            "Próximo TBF ML (h)":   f"{forecast['next_tbf']:.0f}" if forecast["next_tbf"] else "N/A",
            "R(t₀)":                f"{rul['r_current']:.1%}",
            "RUL (h)":              f"{rul['rul_time']:.0f}",
            "Modelo Paramétrico":   best["model_name"],
        }
        html_table(pd.DataFrame(list(info.items()), columns=["Parâmetro", "Valor"]))


def _render_pmo(best, meta):
    with st.expander("ℹ️ Como interpretar — Otimização PMO", expanded=False):
        st.markdown("""
**O que é PMO?**
Preventive Maintenance Optimization — calcula o intervalo de manutenção preventiva que **minimiza o custo por hora** de operação.

**O modelo (Teoria da Renovação):**
Encontra o ponto tp* que equilibra o custo de paradas planejadas (Cp) com o custo de falhas não planejadas (Cu).

**Como usar os inputs:**
- **Cp (Custo Preventivo):** custo relativo de uma parada programada. Use sempre = 1 como referência.
- **Cu (Custo Corretivo):** quantas vezes uma falha não planejada custa mais que uma parada programada.
  - Ex: Cu=5 → falha inesperada custa 5× mais (perda de produção + dano secundário + urgência)
  - Para mineração: Cu/Cp típico entre 5× e 20×

**Como ler o gráfico:**
- Eixo Y = custo por hora de operação
- A curva em U mostra que tanto manutenção muito frequente (custo de paradas) quanto muito espaçada (risco de falha) são ruins
- A estrela vermelha e a linha tracejada marcam o tp* — ponto de custo mínimo

**Resultado principal — tp\*:** a cada quantas horas fazer a manutenção preventiva.
**Redução vs. Corretiva:** quanto você economiza comparado a só consertar quando quebrar.

⚠️ **Disponível apenas para Weibull com β > 1** (desgaste progressivo). Para falhas aleatórias (β ≈ 1), manutenção preventiva por tempo não reduz falhas.
        """)

    beta = best.get("beta")
    eta  = best.get("eta")

    if not beta or not eta or best["dist_type"] != "weibull":
        st.info("ℹ️ PMO disponível apenas quando o melhor ajuste é **Weibull 2P**.")
        return

    if beta <= 1.0:
        st.warning(
            f"⚠️ β = {nbr(beta, 3)} ≤ 1 — Falhas aleatórias. "
            "PMO por substituição por idade **não é economicamente viável**. "
            "Recomenda-se política corretiva ou CBM (Condition-Based Maintenance)."
        )
        return

    st.markdown(f"""
**Modelo de Substituição por Idade** (Age-Based Replacement Policy)

$$C(t_p) = \\frac{{C_p \\cdot R(t_p) + C_u \\cdot F(t_p)}}{{\\int_0^{{t_p}} R(x)\\,dx}}$$

| Parâmetro Weibull | Valor |
|---|---|
| Forma β | {nbr(beta, 3)} |
| Escala η (MTTF) | {nbr(eta, 1)} h |
""")
    st.divider()

    col_cp, col_cu = st.columns(2)
    with col_cp:
        cp = st.number_input("Cp — Custo Preventivo (normalizado)", 1.0, 10.0, 1.0, 0.5,
                             help="Custo relativo de uma parada planejada")
    with col_cu:
        cu = st.number_input("Cu — Custo Corretivo (normalizado)",
                             cp + 0.5, 50.0, max(5.0, cp + 0.5), 0.5,
                             help="Custo relativo de uma falha não planejada")

    with st.spinner("Calculando intervalo ótimo..."):
        pmo = api.pmo(beta=beta, eta=eta, custo_preventivo=cp, custo_corretivo=cu)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Intervalo Ótimo tp*",     f"{pmo['tp_otimo']:.0f} h")
    m2.metric("Disponibilidade em tp*",  f"{pmo['disponibilidade']:.1%}")
    m3.metric("Redução vs. Corretiva",   f"{nbr(pmo['reducao_custo_pct'], 1)}%")
    m4.metric("Relação Cu/Cp",           f"{nbr(cu / cp, 1)}×")

    st.plotly_chart(plot_pmo_curve(pmo), use_container_width=True, config=PLOTLY_CONFIG)

    horas_restantes = max(0, pmo["tp_otimo"] - meta["horimetro_atual"])
    st.markdown(f"""
**📋 Prescrição de Manutenção — {meta['tag']}**

| Ação | Valor |
|---|---|
| Intervalo ótimo de manutenção preventiva | **{pmo['tp_otimo']:.0f} h** |
| Horímetro atual | **{meta['horimetro_atual']:.0f} h** |
| Horas restantes para intervenção | **{horas_restantes:.0f} h** |
| Disponibilidade esperada | **{pmo['disponibilidade']:.1%}** |
| Ganho econômico vs. corretiva | **{nbr(pmo['reducao_custo_pct'], 1)}%** |

> *Válido para regime de desgaste (β={nbr(beta, 2)} > 1). Revisar a cada ciclo com dados atualizados.*
""")
