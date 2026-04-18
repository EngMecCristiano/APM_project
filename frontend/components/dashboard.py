"""
Dashboard superior do APM — bateria de saúde e KPIs calculados.
Todos os valores são derivados dos dados (nenhum hardcoded).
"""
from __future__ import annotations
from frontend.components.ui_helpers import nbr
import streamlit as st
from typing import Dict, Any


def display_header(meta: Dict[str, Any]) -> None:
    st.markdown('<p class="apm-title">ASSET PERFORMANCE MANAGEMENT</p>', unsafe_allow_html=True)
    st.markdown('<p class="apm-subtitle">REAL-TIME ANALYTICS &amp; PREDICTIVE MAINTENANCE</p>', unsafe_allow_html=True)
    st.markdown("---")


def display_health_battery(health_score: int) -> None:
    if health_score >= 70:
        bar_color, glow = "rgba(110,231,183,0.85)", "rgba(110,231,183,0.30)"
    elif health_score >= 40:
        bar_color, glow = "rgba(252,211,77,0.85)",  "rgba(252,211,77,0.30)"
    else:
        bar_color, glow = "rgba(252,129,129,0.85)", "rgba(252,129,129,0.30)"

    st.markdown(f"""
    <div class="battery-container">
        <div class="battery" style="box-shadow: 0 0 14px {glow};">
            <div class="battery-level" style="width:{health_score}%;background:{bar_color};
                 box-shadow: 0 0 10px {glow};"></div>
        </div>
        <div class="health-label">{health_score}% — SAÚDE DO ATIVO</div>
    </div>
    """, unsafe_allow_html=True)


def display_kpi_cards(
    risk_level: str,
    reliability_pct: int,
    horimetro: float,
    audit: Dict[str, Any],
) -> None:
    """
    KPIs calculados a partir do audit (não hardcoded):
    - AVAILABILITY: R(MTTF) × 100  — fração operacional teórica
    - FAILURE RATE: falhas / tempo_total
    - MTBF: parâmetro mttf da distribuição ajustada
    - B10 LIFE: 10° percentil dos TBFs de falha
    - R(t₀): confiabilidade no horímetro atual
    """
    risk_bg, risk_border, risk_text = (
        ("rgba(220,38,38,0.28)",   "rgba(252,129,129,0.60)", "#FCA5A5") if risk_level == "HIGH"
        else ("rgba(202,138,4,0.28)",  "rgba(252,211,77,0.60)",  "#FDE68A") if risk_level == "MEDIUM"
        else ("rgba(16,185,129,0.28)", "rgba(110,231,183,0.60)", "#6EE7B7")
    )

    col2, col3, col4 = st.columns(3)
    with col2:
        st.markdown(f"""
        <div class="metric-card" style="background:{risk_bg};border:1px solid {risk_border};">
            <div class="metric-label">INDICADOR DE RISCO</div>
            <div class="metric-value" style="color:{risk_text};">{risk_level}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card" style="background:rgba(16,185,129,0.22);border:1px solid rgba(110,231,183,0.50);">
            <div class="metric-label">R(t₀) ATUAL</div>
            <div class="metric-value" style="color:#6EE7B7;">{reliability_pct}%</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card" style="background:rgba(0,136,204,0.22);border:1px solid rgba(99,220,247,0.50);">
            <div class="metric-label">HORÍMETRO</div>
            <div class="metric-value" style="color:#63DCF7;">{horimetro:.0f}h</div>
        </div>""", unsafe_allow_html=True)

    # Segunda linha — KPIs derivados do audit
    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (f"{nbr(audit.get('availability_pct', 0), 1)}%",          "DISPONIBILIDADE",  "#A5F3FC", "rgba(0,212,255,0.20)",   "rgba(165,243,252,0.45)"),
        (f"{nbr(audit.get('failure_rate_obs', 0) * 1000, 2)}",    "FALHAS/1000h",  "#FCA5A5", "rgba(220,38,38,0.20)",   "rgba(252,129,129,0.45)"),
        (f"{audit.get('mtbf_h', 0):.0f}h",                    "MTBF",          "#C4B5FD", "rgba(124,58,237,0.20)",  "rgba(196,181,253,0.45)"),
        (f"{audit.get('b10', 0):.0f}h",                       "B10 LIFE",      "#FDE68A", "rgba(202,138,4,0.20)",   "rgba(253,230,138,0.45)"),
        (f"{nbr(audit.get('censure_rate_pct', 0), 1)}%",          "TAXA CENSURA",  "#99F6E4", "rgba(16,185,129,0.20)",  "rgba(153,246,228,0.45)"),
    ]
    for col, (val, label, color, bg, border) in zip([c1, c2, c3, c4, c5], kpis):
        with col:
            st.markdown(f"""
            <div class="metric-card" style="background:{bg};border:1px solid {border};">
                <div class="metric-value" style="font-size:16px;color:{color};">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")


def display_asset_info(meta: Dict[str, Any]) -> None:
    st.markdown(f"""
    <div style="background: rgba(0,0,0,0.45); border-radius: 12px;
                padding: 12px 18px; margin-bottom: 18px;
                border: 1px solid rgba(0,212,255,0.1);">
        <table style="width: 100%; color: #C1E0F5;">
            <tr>
                <td><strong>TAG:</strong> {meta.get('tag','—')}</td>
                <td><strong>Série:</strong> {meta.get('numero_serie','—')}</td>
                <td><strong>Tipo:</strong> {meta.get('tipo_equipamento','—')}</td>
                <td><strong>Data:</strong> {meta.get('data_estudo','—')}</td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)
