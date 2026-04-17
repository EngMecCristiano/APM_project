"""
Aba ML — Machine Learning Prescritivo.
Predição TBF + Detecção de Anomalias + Score de Risco + PMO.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Dict, Any, List

import plotly.graph_objects as go
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
diagnóstico em tempo real e prescrições de manutenção acionáveis via Agente de IA.

| Sub-aba | O que analisa |
|---|---|
| **Predição & Tendência** | Tendência histórica dos TBFs e previsão dos próximos ciclos via Random Forest |
| **Detecção de Anomalias** | Identifica TBFs anômalos (falhas precoces ou outliers) via Isolation Forest |
| **Score de Risco** | Pontuação 0–100 combinando confiabilidade, tendência e anomalias |
| **Otimização PMO** | Intervalo ótimo de manutenção preventiva pela Teoria da Renovação |
| **🤖 Manutenção Prescritiva** | Agente Claude com tool_use gera plano de ação priorizado ISO 14224 |

**Score de Risco:**
- 0–29 → Baixo (verde) — operação normal
- 30–49 → Médio (amarelo) — monitorar
- 50–69 → Alto (laranja) — planejar intervenção
- 70–100 → Crítico (vermelho) — agir imediatamente
        """)

    st.divider()

    # ── Abas ML internas ──────────────────────────────────────────────────────
    tab_pred, tab_anom, tab_risk, tab_pmo, tab_presc = st.tabs([
        "📈 Predição & Tendência",
        "🔍 Detecção de Anomalias",
        "⚠️ Score de Risco",
        "🔧 Otimização PMO",
        "🤖 Manutenção Prescritiva",
    ])

    with tab_pred:
        _render_prediction(trend, forecast, feat_imp, tbf_series, metrics, meta)

    with tab_anom:
        _render_anomalies(anomalies, tbf_series)

    with tab_risk:
        _render_risk(risk, rul, forecast, meta, best)

    with tab_pmo:
        _render_pmo(best, meta)

    with tab_presc:
        _render_prescriptive(ml, fit, rul, records, meta)


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


# ─── Pareto Prescritivo 80/20 ────────────────────────────────────────────────

def _plot_prescriptive_pareto(acoes: list) -> go.Figure:
    """Pareto 80/20 das ações prescritas — barras com degradê criticidade + % acumulada."""
    if not acoes:
        return go.Figure()

    # Ordena por prioridade e agrupa por subcomponente somando custo_relativo
    from collections import defaultdict
    scores: dict = defaultdict(float)
    crits:  dict = {}
    for a in sorted(acoes, key=lambda x: x.get("prioridade", 99)):
        sub   = a.get("subcomponente", "—")
        crit  = a.get("criticidade", "Média")
        custo = float(a.get("custo_relativo", 1.0))
        scores[sub] += custo
        if sub not in crits:
            crits[sub] = crit

    # Ordena decrescente
    labels = sorted(scores, key=lambda k: scores[k], reverse=True)
    vals   = [scores[k] for k in labels]
    total  = sum(vals)
    cum    = [sum(vals[: i + 1]) / total * 100 for i in range(len(vals))]

    # Degradê de cores por criticidade (Alta→Média→Baixa) + posição
    CRIT_BASE = {"Alta": (220, 38, 38), "Média": (59, 130, 246), "Baixa": (16, 185, 129)}
    n = len(labels)
    bar_colors = []
    for i, lbl in enumerate(labels):
        crit = crits.get(lbl, "Média")
        r0, g0, b0 = CRIT_BASE.get(crit, (59, 130, 246))
        # Degrade: 100% intensidade no primeiro, 55% no último
        alpha = 1.0 - (i / max(n - 1, 1)) * 0.45
        r = int(r0 * alpha + 255 * (1 - alpha))
        g = int(g0 * alpha + 255 * (1 - alpha))
        b = int(b0 * alpha + 255 * (1 - alpha))
        bar_colors.append(f"rgb({r},{g},{b})")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels, y=vals,
        name="Custo Relativo",
        marker=dict(color=bar_colors, line=dict(color="rgba(255,255,255,0.15)", width=1)),
        yaxis="y",
        text=[f"{v:.1f}×" for v in vals],
        textposition="outside",
        textfont=dict(size=10, color="#E2E8F0"),
    ))

    fig.add_trace(go.Scatter(
        x=labels, y=cum,
        name="% Acumulada",
        mode="lines+markers+text",
        line=dict(color="#F59E0B", width=2.5),
        marker=dict(size=7, color="#F59E0B",
                    line=dict(color="#0E1117", width=1.5)),
        text=[f"{v:.0f}%" for v in cum],
        textposition="top center",
        textfont=dict(size=9, color="#F59E0B"),
        yaxis="y2",
    ))

    # Linha 80%
    fig.add_hline(
        y=80, line_dash="dash", line_color="#DC2626", line_width=1.5,
        annotation_text="80% — Regra de Pareto",
        annotation_position="top right",
        annotation_font=dict(color="#DC2626", size=10),
        yref="y2",
    )

    fig.update_layout(
        title=dict(
            text="Análise de Pareto — Impacto por Subcomponente (Custo Relativo × Criticidade)",
            font=dict(size=13, color="#E2E8F0"),
        ),
        plot_bgcolor="#0E1117",
        paper_bgcolor="#0E1117",
        font=dict(color="#E2E8F0"),
        xaxis=dict(tickangle=-30, showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(
            title="Custo Relativo Acumulado",
            gridcolor="#1E293B",
            titlefont=dict(size=10),
        ),
        yaxis2=dict(
            title="% Acumulada",
            overlaying="y", side="right",
            range=[0, 115],
            showgrid=False,
            titlefont=dict(size=10),
        ),
        legend=dict(orientation="h", y=1.14, x=0, font=dict(size=10)),
        margin=dict(t=70, b=70, l=50, r=60),
        bargap=0.25,
    )
    return fig


# ─── Manutenção Prescritiva com Agente de IA ──────────────────────────────────

def _render_prescriptive(
    ml: Dict[str, Any],
    fit: Dict[str, Any],
    rul: Dict[str, Any],
    records: List[Dict],
    meta: Dict[str, Any],
) -> None:

    with st.expander("ℹ️ Como funciona o Agente de Manutenção Prescritiva", expanded=False):
        st.markdown("""
### O que é Manutenção Prescritiva com IA?

A manutenção prescritiva vai além do diagnóstico: não apenas detecta o risco, mas **prescreve ações
específicas** com prioridade, janela de intervenção e justificativa técnica.

### Arquitetura do Agente

```
Dados do Ativo ──► Agente Claude (claude-opus-4-7)
                        │
              ┌─────────┼──────────┐
              ▼         ▼          ▼
    get_catalog    compute_      classify_
    _scenarios     maintenance   urgency
                   _window
              │         │          │
              └─────────┴──────────┘
                        │
                        ▼
              Plano Prescritivo ISO 14224
```

### Ferramentas do Agente

| Ferramenta | O que faz |
|---|---|
| `get_catalog_scenarios` | Busca os modos de falha mais críticos e prováveis no catálogo ISO 14224 |
| `compute_maintenance_window` | Calcula a janela de intervenção com base no RUL + Score de Risco + PMO |
| `classify_urgency` | Define o nível de urgência: Crítica / Alta / Média / Baixa |

O agente raciocina em múltiplos passos, chama as ferramentas que julgar necessárias
e sintetiza tudo em um **plano de ação priorizado com justificativas técnicas**.

### Passo a Passo para Usar

1. **Execute a análise completa** — clique em Executar / Processar na sidebar
2. **Aguarde o carregamento** de todas as abas (LDA, RUL, ML)
3. **Acesse esta sub-aba** — Manutenção Prescritiva
4. **Clique em "Gerar Prescrição com IA"**
5. O agente analisa: score de risco · RUL · tendência · catálogo ISO 14224
6. **Revise o plano prescritivo** — prioridades, ações e janelas de intervenção

> **Sem ANTHROPIC_API_KEY:** O sistema usa Expert System baseado em regras ISO 14224
> (sem custo, sem API externa) como fallback automático.
        """)

    risk  = ml["risk"]
    trend = ml["trend"]
    best  = fit["best"]

    # ── Estado atual do ativo ─────────────────────────────────────────────────
    urgency_colors = {"Crítica": "#DC2626", "Alta": "#F59E0B", "Média": "#3B82F6", "Baixa": "#10B981"}
    risk_color = urgency_colors.get(risk["classification"], "#3B82F6")

    st.markdown("### Estado Atual do Ativo")
    kpi_row([
        ("Score de Risco",    f"{risk['score']}/100",          risk["classification"]),
        ("RUL Estimado",      f"{rul['rul_time']:.0f} h",       f"R(t)={rul['r_current']:.1%}"),
        ("Tendência",         trend["trend_type"][:20],         f"{nbr(trend['degradation_rate'], 2)}%/ciclo"),
        ("Horímetro",         f"{meta['horimetro_atual']:.0f} h", meta["tag"]),
    ])

    st.markdown("---")

    # ── Botão para gerar prescrição ───────────────────────────────────────────
    pmo_tp = st.session_state.get("_pmo_tp_otimo")

    if st.button(
        "🤖 Gerar Prescrição com IA",
        type="primary",
        use_container_width=True,
        help="O agente Claude analisa os dados e gera um plano prescritivo ISO 14224",
    ):
        with st.spinner("🤖 Agente analisando dados do ativo…"):
            try:
                result = api.prescriptive_agent(
                    equipment_type      = meta["tipo_equipamento"],
                    risk_score          = int(risk["score"]),
                    risk_classification = risk["classification"],
                    rul_hours           = float(rul["rul_time"]),
                    horimetro_atual     = float(meta["horimetro_atual"]),
                    failure_count       = sum(1 for r in records if r.get("Falha") == 1),
                    anomaly_count       = int(ml["anomalies"]["count"]),
                    trend_type          = trend["trend_type"],
                    degradation_rate    = float(trend["degradation_rate"]),
                    tag                 = meta["tag"],
                    weibull_beta        = best.get("beta"),
                    weibull_eta         = best.get("eta"),
                    pmo_tp_otimo        = pmo_tp,
                    meta                = meta,
                )
                st.session_state["_prescriptive_result"] = result
            except Exception as e:
                st.error(f"❌ Erro ao gerar prescrição: {e}")
                return

    result = st.session_state.get("_prescriptive_result")
    if not result:
        st.info(
            "Clique em **🤖 Gerar Prescrição com IA** para iniciar o agente."
        )
        return

    # ── Exibição do resultado ─────────────────────────────────────────────────
    nivel    = result.get("nivel_urgencia", "Média")
    cor      = result.get("cor_urgencia", urgency_colors.get(nivel, "#3B82F6"))
    janela   = result.get("janela_intervencao", "—")
    hs       = result.get("proxima_intervencao_h")
    ia_ativa = result.get("ia_disponivel", False)

    # Badge de modo
    if ia_ativa:
        st.success("Prescrição gerada pelo **Agente Claude** (claude-sonnet-4-6 + tool_use)", icon="🤖")
    else:
        st.info("Prescrição gerada pelo **Expert System** (ANTHROPIC_API_KEY não configurada)", icon="⚙️")

    # Sumário executivo com badge de urgência
    janela_html = ""
    if janela != "—":
        hs_str = f" — {hs:.0f}h" if hs else ""
        janela_html = f'<br/><span style="color:#94A3B8;font-size:13px;">Janela: {janela}{hs_str}</span>'
    sumario = result.get("sumario_executivo", "")
    st.markdown(
        f'<div style="background:{cor}22;border-left:5px solid {cor};'
        f'padding:14px 18px;border-radius:6px;margin:12px 0;">'
        f'<span style="font-size:18px;font-weight:700;color:{cor};">{nivel}</span>'
        f'<br/><span style="color:#E2E8F0;font-size:14px;">{sumario}</span>'
        f'{janela_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Diagnóstico técnico — campo já vem limpo (sem JSON) do backend
    diagnostico = result.get("diagnostico", "")
    if diagnostico:
        with st.expander("📋 Diagnóstico Técnico Completo", expanded=True):
            st.markdown(diagnostico)

    # Raciocínio do agente
    steps = result.get("raciocinio_agente", [])
    if steps:
        with st.expander(f"🔍 Raciocínio do Agente ({len(steps)} passo(s))", expanded=False):
            for s in steps:
                st.caption(s)

    # Tabela de ações priorizadas
    acoes = result.get("acoes", [])
    if acoes:
        st.markdown(f"### Plano de Ação Prescritivo — {len(acoes)} Intervenção(ões)")

        # ── Pareto 80/20 com degradê de cores ────────────────────────────────
        st.plotly_chart(
            _plot_prescriptive_pareto(acoes),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )

        crit_colors = {"Alta": "🔴", "Média": "🟡", "Baixa": "🟢"}

        rows = []
        for a in acoes:
            rows.append({
                "Pri.":           f"#{a.get('prioridade', '—')}",
                "Subcomponente":  a.get("subcomponente", "—"),
                "Modo de Falha":  a.get("modo_falha", "—"),
                "Causa Raiz":     a.get("causa_raiz", "—"),
                "Criticidade":    crit_colors.get(a.get("criticidade", "—"), "⚪") + " " + a.get("criticidade", "—"),
                "Boundary":       a.get("boundary", "—"),
                "Janela":         a.get("janela_intervencao", "—"),
                "TTR Esp. (h)":   f"{a.get('ttr_esperado_h', '—')}",
                "Custo Rel.":     f"{a.get('custo_relativo', 1.0):.1f}×",
            })

        html_table(pd.DataFrame(rows))

        # Detalhes de cada ação
        st.markdown("#### Detalhes das Ações")
        for a in acoes:
            crit_icon = crit_colors.get(a.get("criticidade", "—"), "⚪")
            with st.expander(
                f"{crit_icon} #{a.get('prioridade')} — {a.get('subcomponente','—')} · {a.get('modo_falha','—')}",
                expanded=(a.get("prioridade") == 1),
            ):
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown(f"**Subcomponente:** {a.get('subcomponente','—')}")
                    st.markdown(f"**Modo de Falha:** {a.get('modo_falha','—')}")
                    st.markdown(f"**Causa Raiz:** {a.get('causa_raiz','—')}")
                    st.markdown(f"**Mecanismo:** {a.get('mecanismo','—')}")
                with col_r:
                    st.markdown(f"**Criticidade:** {crit_icon} {a.get('criticidade','—')}")
                    st.markdown(f"**Boundary:** {a.get('boundary','—')}")
                    st.markdown(f"**Janela:** {a.get('janela_intervencao','—')}")
                    if a.get("ttr_esperado_h"):
                        st.markdown(f"**TTR Esperado:** {a['ttr_esperado_h']} h")
                st.info(f"**Ação:** {a.get('acao_recomendada','—')}")
                if a.get("justificativa"):
                    st.caption(f"Justificativa: {a['justificativa']}")
    else:
        st.warning("Nenhuma ação prescrita — verifique os dados de entrada.")
