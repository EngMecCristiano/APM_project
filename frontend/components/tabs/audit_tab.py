"""
Aba Auditoria — EDA + Validação estatística + Taxonomia ISO 14224.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from typing import Dict, Any, List, Optional

import frontend.api_client as api
from frontend.components.charts import plot_tbf_histogram, plot_boxplot, plot_qq
from frontend.components.ui_helpers import nbr, kpi_row, html_table
from frontend.styles.theme import PLOTLY_CONFIG


def render(audit: Dict[str, Any], records: List[Dict], meta: Dict[str, Any]) -> None:

    with st.expander("ℹ️ Como interpretar esta aba — EDA + Auditoria Estatística", expanded=False):
        st.markdown("""
**O que esta aba faz?**
Valida a qualidade dos dados e avalia o quanto o modelo ajustado representa bem o comportamento real do equipamento.

---

**Análise Exploratória (EDA)**

| Gráfico | O que analisar |
|---|---|
| **Distribuição (histograma)** | Formato da curva: simétrico, assimétrico à direita (típico de Weibull), bimodal (duas populações de falha) |
| **Boxplot** | Comparar mediana e dispersão entre falhas e censuras. Outliers como pontos isolados |
| **Estatísticas** | Média, mediana, desvio padrão, mínimo e máximo dos TBFs |

---

**Auditoria de Confiabilidade**

| Métrica | Como interpretar |
|---|---|
| **B10 / B50 / B90** | Tempo em que 10% / 50% / 90% dos equipamentos terão falhado. B50 = mediana de vida |
| **Disponibilidade** | Percentual do tempo esperado que o equipamento opera sem falhar (baseado no MTTF) |
| **QQ Plot** | Pontos próximos à diagonal = bom ajuste do modelo aos dados reais |
| **KS p-value** | p > 0.05 = modelo não rejeitado estatisticamente; p < 0.05 = ajuste suspeito |

---

**Diagnóstico Avançado**

| Indicador | Como interpretar |
|---|---|
| **Outliers IQR** | TBFs muito curtos = mortalidade infantil; muito longos = possível censura não registrada |
| **ρ Spearman** | Correlação entre ordem cronológica e TBF. Negativo + significativo = degradação ao longo do tempo |
        """)

    # ── EDA — KPIs ───────────────────────────────────────────────────────────
    st.markdown("### Análise Exploratória de Dados")
    kpi_row([
        ("Total Registros", str(audit["n_total"]),        "eventos"),
        ("Total Falhas",    str(audit["n_failures"]),     "status = 1"),
        ("Total Censuras",  str(audit["n_censored"]),     "status = 0"),
        ("TBF Médio",       f"{nbr(audit['tbf_mean'], 1)} h", "aritmético"),
    ])

    tab_hist, tab_box, tab_stats = st.tabs(["Distribuição", "Boxplot", "Estatísticas"])

    with tab_hist:
        tbf_all = [r["TBF"] for r in records]
        st.plotly_chart(plot_tbf_histogram(tbf_all), use_container_width=True, config=PLOTLY_CONFIG)

    with tab_box:
        tbf_fail = [r["TBF"] for r in records if r["Falha"] == 1]
        tbf_cens = [r["TBF"] for r in records if r["Falha"] == 0]
        st.plotly_chart(plot_boxplot(tbf_fail, tbf_cens), use_container_width=True, config=PLOTLY_CONFIG)

    with tab_stats:
        df_tmp = pd.DataFrame(records)
        html_table(df_tmp.describe().round(2).reset_index().rename(columns={"index": "Estatística"}))

    df_dl = pd.DataFrame(records)
    st.download_button(
        "📥 Download CSV",
        data=df_dl.to_csv(index=False).encode(),
        file_name=f"apm_{meta['tag']}.csv",
        mime="text/csv",
    )

    st.divider()

    # ── Auditoria de Confiabilidade ───────────────────────────────────────────
    st.markdown("### Auditoria de Confiabilidade")

    tab_v, tab_p, tab_r, tab_d = st.tabs([
        "Validação de Modelos",
        "Métricas de Performance",
        "QQ Plot & KS",
        "Diagnóstico Avançado",
    ])

    with tab_v:
        _render_model_validation(audit)
    with tab_p:
        _render_performance(audit)
    with tab_r:
        _render_residuals(audit)
    with tab_d:
        _render_diagnostics(audit)

    st.divider()

    # ── Taxonomia ISO 14224 ───────────────────────────────────────────────────
    _render_taxonomy(meta)


def _render_model_validation(audit):
    st.markdown("#### KPIs de Confiabilidade")
    kpi_row([
        ("R(MTTF)",               f"{audit['reliability_at_mttf']:.1%}", "Confiabilidade no MTTF"),
        ("MTBF (dist. ajustada)", f"{nbr(audit['mtbf_h'], 1)} h",            "Esperança de vida"),
        ("Disponibilidade",       f"{nbr(audit['availability_pct'], 1)}%",   "R(MTTF) × 100"),
    ])

    st.markdown("#### B-Lives")
    kpi_row([
        ("B10 Life", f"{nbr(audit['b10'], 1)} h", "10% falham antes de"),
        ("B50 Life", f"{nbr(audit['b50'], 1)} h", "Mediana dos TBFs"),
        ("B90 Life", f"{nbr(audit['b90'], 1)} h", "90% falham antes de"),
    ])

    st.markdown("#### Percentis Completos")
    html_table(
        pd.DataFrame(audit["percentiles"]).rename(columns={
            "percentile": "Percentil (%)", "tbf_h": "TBF (h)", "label": "Interpretação"
        })
    )


def _render_performance(audit):
    kpi_row([
        ("Taxa de Falha",  f"{nbr(audit['failure_rate_obs'] * 1000, 3)}", "falhas / 1000 h"),
        ("Taxa de Censura", f"{nbr(audit['censure_rate_pct'], 1)}%",      "registros sem falha"),
        ("Hazard h(t₀)",   f"{nbr(audit['hazard_at_current'], 6)}",       "falhas/h no horímetro atual"),
    ])


def _render_residuals(audit):
    st.markdown(f"#### QQ Plot — {audit['ks_model']} vs. Dados Observados")
    st.plotly_chart(
        plot_qq(audit["qq_theoretical"], audit["qq_observed"], audit["ks_model"]),
        use_container_width=True,
        config=PLOTLY_CONFIG,
    )

    st.markdown(f"#### Teste KS — Aderência ao Melhor Modelo ({audit['ks_model']})")
    kpi_row([
        ("KS Statistic", f"{nbr(audit['ks_stat'], 4)}", "quanto menor, melhor"),
        ("KS p-value",   f"{nbr(audit['ks_p'], 4)}",   "rejeitar se p < 0.05"),
    ])

    if audit["ks_p"] > 0.05:
        st.success(f"✅ **{audit['ks_model']}** NÃO rejeitada (p > 0.05)")
    else:
        st.warning(f"⚠️ **{audit['ks_model']}** pode ser rejeitada (p < 0.05)")


def _render_diagnostics(audit):
    st.markdown("#### Outliers — Método IQR")
    kpi_row([
        ("Outliers Detectados", str(audit["n_outliers"]),          "via IQR"),
        ("% do Total",          f"{nbr(audit['outlier_pct'], 1)}%",    "proporção"),
        ("Limites IQR",
         f"[{audit['outlier_lower']:.0f}, {audit['outlier_upper']:.0f}] h",
         "intervalo de referência"),
    ])
    if audit["n_outliers"] > 0:
        st.info("💡 Outliers baixos → mortalidade infantil | Altos → possível censura não registrada")

    st.markdown("#### Tendência Temporal — Spearman")
    kpi_row([
        ("ρ Spearman", f"{nbr(audit['spearman_corr'], 4)}", "correlação rank"),
        ("p-value",    f"{nbr(audit['spearman_p'], 4)}",    "< 0.05 = significativo"),
    ])

    if audit["spearman_p"] < 0.05:
        if audit["spearman_corr"] < 0:
            st.error("🔴 Tendência de degradação — TBF diminuindo sistematicamente.")
        else:
            st.success("🟢 Tendência de melhoria — TBF aumentando ao longo do tempo.")
    else:
        st.info("ℹ️ Sem tendência significativa — processo estacionário.")


# ─── Taxonomia ISO 14224 ──────────────────────────────────────────────────────

def _plot_pareto(series: pd.Series, title: str, top_n: int = 12) -> go.Figure:
    """Pareto: barras de contagem + linha de % acumulada + referência 80%."""
    counts = series.value_counts().head(top_n)
    labels = counts.index.tolist()
    vals   = counts.values.tolist()
    total  = sum(vals)
    cum    = [sum(vals[: i + 1]) / total * 100 for i in range(len(vals))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=vals,
        name="Ocorrências",
        marker_color="#00D4FF",
        opacity=0.85,
        yaxis="y",
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=cum,
        name="% Acumulada",
        mode="lines+markers",
        line=dict(color="#F59E0B", width=2),
        marker=dict(size=6),
        yaxis="y2",
    ))
    fig.add_hline(
        y=80, line_dash="dash", line_color="#DC2626",
        annotation_text="80%", annotation_position="right",
        yref="y2",
    )
    fig.update_layout(
        title=title,
        plot_bgcolor="#0E1117",
        paper_bgcolor="#0E1117",
        font=dict(color="#E2E8F0"),
        xaxis=dict(tickangle=-35, showgrid=False),
        yaxis=dict(title="Ocorrências", gridcolor="#1E293B"),
        yaxis2=dict(
            title="% Acumulada",
            overlaying="y",
            side="right",
            range=[0, 110],
            showgrid=False,
        ),
        legend=dict(orientation="h", y=1.12, x=0),
        margin=dict(t=60, b=80),
    )
    return fig


def _render_taxonomy(meta: Dict[str, Any]) -> None:
    """Pareto e estatísticas dos modos de falha a partir do histórico ISO 14224 salvo."""
    st.markdown("### 🏷️ Taxonomia ISO 14224 — Análise de Modos de Falha")

    tag = meta.get("tag", "")
    rich: Optional[List[Dict]] = None

    try:
        rich = api.history_load_rich(tag)
    except Exception as e:
        st.warning(f"Não foi possível carregar histórico ISO 14224: {e}")

    if not rich:
        st.info(
            f"Sem dados ISO 14224 para TAG **{tag}**. "
            "Para gerar esta análise:\n\n"
            "1. Use o modo **Entrada Manual (ISO 14224)** na sidebar e salve eventos com taxonomia completa\n"
            "2. Ou use a **Simulação Enriquecida** que gera automaticamente todos os campos ISO 14224"
        )
        return

    df = pd.DataFrame(rich)
    # Filtra apenas falhas confirmadas para o Pareto
    df_falhas = df[df.get("Falha", df.get("falha", pd.Series())).astype(int) == 1] if "Falha" in df.columns else df

    n_total  = len(df)
    n_falhas = len(df_falhas)
    st.caption(f"TAG **{tag}** — {n_total} registros ISO 14224 ({n_falhas} falhas confirmadas)")

    if n_falhas == 0:
        st.info("Nenhuma falha confirmada nos registros ISO 14224. Pareto indisponível.")
        return

    # KPIs de taxonomia
    kpi_row([
        ("Registros ISO 14224", str(n_total),   "histórico rico"),
        ("Falhas Confirmadas",  str(n_falhas),  "Falha = 1"),
        ("Modos de Falha",      str(df_falhas["Modo_Falha"].nunique()) if "Modo_Falha" in df_falhas.columns else "—", "únicos"),
        ("Subcomponentes",      str(df_falhas["Subcomponente"].nunique()) if "Subcomponente" in df_falhas.columns else "—", "únicos"),
    ])

    # Tabs dos gráficos de Pareto
    tab_modo, tab_sub, tab_causa, tab_bound, tab_crit = st.tabs([
        "Modos de Falha",
        "Subcomponentes",
        "Causa Raiz",
        "Boundary",
        "Criticidade",
    ])

    with tab_modo:
        if "Modo_Falha" in df_falhas.columns:
            st.plotly_chart(
                _plot_pareto(df_falhas["Modo_Falha"], "Pareto — Modos de Falha"),
                use_container_width=True, config=PLOTLY_CONFIG,
            )
            st.caption("Os modos à esquerda da linha 80% causam 80% das falhas — foco de priorização.")
        else:
            st.info("Coluna Modo_Falha não encontrada nos registros.")

    with tab_sub:
        if "Subcomponente" in df_falhas.columns:
            st.plotly_chart(
                _plot_pareto(df_falhas["Subcomponente"], "Pareto — Subcomponentes"),
                use_container_width=True, config=PLOTLY_CONFIG,
            )
        else:
            st.info("Coluna Subcomponente não encontrada nos registros.")

    with tab_causa:
        if "Causa_Raiz" in df_falhas.columns:
            st.plotly_chart(
                _plot_pareto(df_falhas["Causa_Raiz"], "Pareto — Causas Raiz"),
                use_container_width=True, config=PLOTLY_CONFIG,
            )
        else:
            st.info("Coluna Causa_Raiz não encontrada nos registros.")

    with tab_bound:
        if "Boundary" in df_falhas.columns:
            counts = df_falhas["Boundary"].value_counts()
            total  = counts.sum()
            fig_pie = go.Figure(go.Pie(
                labels=counts.index.tolist(),
                values=counts.values.tolist(),
                hole=0.45,
                marker=dict(colors=["#00D4FF", "#F59E0B"]),
                textinfo="label+percent",
            ))
            fig_pie.update_layout(
                title="Boundary — Interno vs. Externo",
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                font=dict(color="#E2E8F0"),
                showlegend=True,
            )
            st.plotly_chart(fig_pie, use_container_width=True, config=PLOTLY_CONFIG)
            st.caption(
                "**Interno:** falha originada dentro do equipamento. "
                "**Externo:** causa no processo, ambiente ou interface."
            )
        else:
            st.info("Coluna Boundary não encontrada nos registros.")

    with tab_crit:
        if "Criticidade" in df_falhas.columns:
            counts = df_falhas["Criticidade"].value_counts().reindex(["Alta", "Média", "Baixa"]).dropna()
            colors = ["#DC2626", "#F59E0B", "#10B981"]
            fig_bar = go.Figure(go.Bar(
                x=counts.index.tolist(),
                y=counts.values.tolist(),
                marker_color=colors[: len(counts)],
                text=counts.values.tolist(),
                textposition="outside",
            ))
            fig_bar.update_layout(
                title="Distribuição de Criticidade das Falhas",
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                font=dict(color="#E2E8F0"),
                xaxis=dict(showgrid=False),
                yaxis=dict(title="Ocorrências", gridcolor="#1E293B"),
            )
            st.plotly_chart(fig_bar, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("Coluna Criticidade não encontrada nos registros.")

    # Download do histórico rico
    st.download_button(
        "📥 Download Histórico ISO 14224 (CSV)",
        data=df.to_csv(index=False).encode(),
        file_name=f"iso14224_{tag}.csv",
        mime="text/csv",
    )
