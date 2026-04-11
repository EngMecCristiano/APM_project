"""
Sidebar de configuração do APM.
Retorna (AssetMeta dict, records List[dict], triggered bool, rich_df DataFrame|None).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import frontend.api_client as api

EQUIPMENT_TYPES = [
    "Britador Cônico",
    "Peneira Vibratória",
    "Bomba de Polpa",
    "Transportador de Correia",
]


def render_sidebar() -> Tuple[
    Optional[Dict[str, Any]],
    Optional[List[Dict]],
    bool,
    Optional[pd.DataFrame],
]:
    """
    Renderiza a sidebar e retorna (meta, records, triggered, rich_df).
    - records: lista slim {TBF, Tempo_Acumulado, Falha} para o pipeline de análise
    - rich_df: DataFrame completo (25 col) apenas quando modo Enriquecido
    """
    with st.sidebar:
        st.markdown(
            '<p style="font-size:17px;font-weight:700;color:#DEF7FF;margin:0 0 4px 0;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            '🚜 Configuração do Estudo</p>'
            '<br>',
            unsafe_allow_html=True,
        )
        st.divider()

        tipo_eq  = st.selectbox("Classe do Ativo", EQUIPMENT_TYPES)
        tag_eq   = st.text_input("TAG Operacional", value="BRT-01A")
        serie_eq = st.text_input("Número de Série", value="SN-998822",
                                 help="Identificador único para rastreabilidade.")
        h_atual  = st.number_input("Horímetro Atual (h)", value=800.0, step=100.0)

        meta: Dict[str, Any] = {
            "tag":              tag_eq,
            "nome":             "Equipamento",
            "numero_serie":     serie_eq,
            "tipo_equipamento": tipo_eq,
            "horimetro_atual":  float(h_atual),
            "data_estudo":      datetime.now().strftime("%Y-%m-%d"),
        }

        _render_history_panel(tag_eq, meta)

        st.divider()
        st.markdown(
            '<p style="font-size:13px;font-weight:600;color:#DEF7FF;'
            'margin:0 0 6px 0;letter-spacing:0.5px;">Modo de Entrada</p>',
            unsafe_allow_html=True,
        )
        mode = st.radio(
            "Modo de Entrada",
            ["Simulador Paramétrico", "Simulação Enriquecida (ISO 14224)", "Importar CSV Real"],
            label_visibility="collapsed",
        )
        st.divider()

        if mode == "Simulador Paramétrico":
            return _render_simulator(meta, tipo_eq)
        elif mode == "Simulação Enriquecida (ISO 14224)":
            return _render_rich_simulator(meta, tipo_eq, tag_eq)
        else:
            return _render_upload(meta)


def _render_history_panel(tag: str, meta: Dict[str, Any]) -> None:
    """Painel de histórico acumulado — mostra registros existentes e opção de usar/limpar."""
    try:
        hist = api.history_load(tag)
    except Exception:
        hist = None

    if hist:
        n = len(hist)
        with st.expander(f"📂 Histórico: {n} registros acumulados", expanded=False):
            st.caption(f"TAG **{tag}** possui {n} TBFs persistidos de sessões anteriores.")
            use_hist = st.checkbox(
                "Incluir histórico na análise",
                value=True,
                key="use_history",
                help="Combina os dados novos com o histórico para treinar com mais dados.",
            )
            st.session_state["history_records"] = hist if use_hist else None

            if st.button("🗑️ Apagar histórico", key="del_history"):
                try:
                    api.history_delete(tag)
                    st.session_state["history_records"] = None
                    st.success("Histórico removido.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
    else:
        st.session_state["history_records"] = None
        st.caption(f"📂 Sem histórico para **{tag}** — será criado após a primeira análise.")


def _render_thresholds() -> None:
    """Expander de limiares — persiste valores no session_state."""
    with st.expander("⚙️ Limiares de Análise", expanded=False):
        st.caption("Ajuste os critérios de alerta e de RUL para este ativo.")

        rul_pct = st.slider(
            "Limiar RUL (confiabilidade mínima)",
            min_value=0, max_value=100, value=10, step=5,
            format="%d%%",
            help="RUL é calculado até a confiabilidade condicional cair abaixo deste valor.",
        )

        st.markdown("**Limiares de Risco ML** (pontuação 0–100)")
        st.caption("BAIXO → MÉD → ALTO → CRIT ≤ 100")
        c1, c2, c3 = st.columns(3)
        with c1:
            risk_medio = st.number_input(
                "MÉD ≥",
                min_value=5, max_value=60, value=30, step=5,
                help="Score ≥ este valor → risco MÉDIO.",
            )
        with c2:
            risk_alto = st.number_input(
                "ALTO ≥",
                min_value=risk_medio + 5, max_value=85, value=max(50, risk_medio + 5), step=5,
                help="Score ≥ este valor → risco ALTO.",
            )
        with c3:
            risk_critical = st.number_input(
                "CRIT ≥",
                min_value=risk_alto + 5, max_value=95, value=max(70, risk_alto + 5), step=5,
                help="Score ≥ este valor → risco CRÍTICO.",
            )

        n_bootstrap = st.select_slider(
            "Bootstrap RUL (amostras)",
            options=[50, 100, 200, 300, 500, 1000],
            value=300,
            help="Número de reamostragens para o IC do RUL. Mais amostras = mais preciso, porém mais lento.",
        )

        # Persiste no session_state para app.py usar
        st.session_state["rul_threshold"] = rul_pct / 100.0
        st.session_state["n_bootstrap"]   = int(n_bootstrap)
        st.session_state["risk_thresholds"] = {
            "critical": int(risk_critical),
            "alto":     int(risk_alto),
            "medio":    int(risk_medio),
        }


# ─── Simulador básico ─────────────────────────────────────────────────────────

def _render_simulator(
    meta: Dict[str, Any], tipo_eq: str
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, None]:
    col1, col2 = st.columns(2)
    with col1:
        n = st.slider("Amostras", 100, 1500, 500, 50)
    with col2:
        n = st.number_input("Valor exato", 100, 1500, n, 50, key="n_exact")

    noise   = st.slider("Ruído Gaussiano (%)",     0.0, 50.0, 15.0, 1.0)
    outlier = st.slider("Mortalidade Infantil (%)", 0.0, 20.0,  5.0, 1.0)
    aging   = st.slider("Fadiga Sistêmica (%)",     0.0,  5.0,  1.5, 0.1)
    st.divider()

    _render_thresholds()

    if st.button("▶ Executar Simulação", type="primary", use_container_width=True):
        with st.spinner("Gerando dados simulados..."):
            records = api.simulate(int(n), tipo_eq, noise, outlier, aging)
        st.success(f"✅ {len(records)} registros gerados.")
        return meta, records, True, None

    return meta, None, False, None


# ─── Simulador enriquecido ────────────────────────────────────────────────────

def _render_rich_simulator(
    meta: Dict[str, Any], tipo_eq: str, tag_eq: str
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, Optional[pd.DataFrame]]:

    st.caption("Gera dataset completo: modo de falha, causa raiz, TTR, datas, custo e produção perdida.")

    col1, col2 = st.columns(2)
    with col1:
        n = st.slider("Amostras", 100, 1500, 500, 50, key="rich_n")
    with col2:
        n = st.number_input("Valor exato", 100, 1500, n, 50, key="rich_n_exact")

    noise   = st.slider("Ruído Gaussiano (%)",     0.0, 50.0, 15.0, 1.0, key="rich_noise")
    outlier = st.slider("Mortalidade Infantil (%)", 0.0, 20.0,  5.0, 1.0, key="rich_out")
    aging   = st.slider("Fadiga Sistêmica (%)",     0.0,  5.0,  1.5, 0.1, key="rich_aging")
    st.divider()

    start_date  = st.date_input("Data de Início do Histórico", value=datetime(2021, 1, 1))
    preco_t     = st.number_input("Valor do Produto (R$/t)", value=45.0, step=5.0,
                                  help="Usado para calcular lucro cessante por parada.")

    _render_thresholds()

    if st.button("▶ Gerar Dataset Enriquecido", type="primary", use_container_width=True):
        with st.spinner("Gerando dados com taxonomia ISO 14224..."):
            raw = api.simulate_rich(
                n_samples=int(n),
                equipment_type=tipo_eq,
                noise_pct=noise,
                outlier_pct=outlier,
                aging_pct=aging,
                tag_ativo=tag_eq,
                start_date=start_date.strftime("%Y-%m-%d"),
                preco_produto_brl_t=float(preco_t),
            )

        rich_df = pd.DataFrame(raw)

        # Records slim para o pipeline de análise (apenas TBF, Tempo_Acumulado, Falha)
        records = [
            {"TBF": r["TBF"], "Tempo_Acumulado": r["Tempo_Acumulado"], "Falha": r["Falha"]}
            for r in raw
        ]

        st.success(
            f"✅ {len(records)} eventos | "
            f"{int(rich_df['Falha'].sum())} falhas | "
            f"{len(rich_df['Modo_Falha'].unique())} modos de falha"
        )
        return meta, records, True, rich_df

    return meta, None, False, None


# ─── Upload CSV ───────────────────────────────────────────────────────────────

def _render_upload(
    meta: Dict[str, Any]
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, None]:
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file is None:
        return meta, None, False, None

    file_bytes = file.read()

    with st.spinner("Lendo colunas..."):
        info = api.get_csv_columns(file_bytes, file.name)

    cols    = info.get("columns", [])
    n_rows  = info.get("n_rows", 0)
    st.caption(f"Arquivo: {n_rows} linhas × {len(cols)} colunas")

    if n_rows < 100:
        st.error(f"❌ Mínimo 100 registros. Arquivo tem {n_rows}.")
        return meta, None, False, None

    t_col = st.selectbox("Coluna de Tempo (TBF)", cols)
    s_col = st.selectbox("Coluna de Status (Falha=1)", cols)

    _render_thresholds()

    if st.button("▶ Processar Dados Reais", type="primary", use_container_width=True):
        with st.spinner("Processando CSV..."):
            records = api.upload_csv(file_bytes, file.name, t_col, s_col)
        st.success(f"✅ {len(records)} registros processados.")
        return meta, records, True, None

    return meta, None, False, None
