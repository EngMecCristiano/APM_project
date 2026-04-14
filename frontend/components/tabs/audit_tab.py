"""
Aba Auditoria — EDA + Validação estatística.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from typing import Dict, Any, List

from frontend.components.charts import plot_tbf_histogram, plot_boxplot, plot_qq
from frontend.components.ui_helpers import nbr, kpi_row, html_table


def render(audit: Dict[str, Any], records: List[Dict], meta: Dict[str, Any]) -> None:

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
        st.plotly_chart(plot_tbf_histogram(tbf_all), use_container_width=True)

    with tab_box:
        tbf_fail = [r["TBF"] for r in records if r["Falha"] == 1]
        tbf_cens = [r["TBF"] for r in records if r["Falha"] == 0]
        st.plotly_chart(plot_boxplot(tbf_fail, tbf_cens), use_container_width=True)

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
