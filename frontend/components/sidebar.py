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
    "Outro (personalizado)",
]

# Parâmetros Weibull padrão para equipamento personalizado
CUSTOM_BETA_DEFAULT = 1.5
CUSTOM_ETA_DEFAULT  = 1000.0
CUSTOM_MU_DEFAULT   = 6.5    # ln(665 h) ≈ mediana ~665 h
CUSTOM_SIGMA_DEFAULT = 0.8


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

        tipo_sel = st.selectbox("Classe do Ativo", EQUIPMENT_TYPES)

        # ── Equipamento personalizado ─────────────────────────────────────────
        custom_beta:  Optional[float] = None
        custom_eta:   Optional[float] = None
        custom_mu:    Optional[float] = None
        custom_sigma: Optional[float] = None
        custom_dist:  Optional[str]   = None

        if tipo_sel == "Outro (personalizado)":
            tipo_eq = st.text_input(
                "Nome do Equipamento",
                value="",
                placeholder="ex: Compressor de Ar, Turbina a Vapor...",
            )
            with st.expander("⚙️ Parâmetros do Simulador", expanded=True):
                custom_dist = st.radio(
                    "Distribuição base",
                    ["Weibull", "Lognormal"],
                    horizontal=True,
                    help="Define a distribuição usada para gerar os TBFs sintéticos.",
                )

                if custom_dist == "Weibull":
                    st.caption("Weibull — adequada para desgaste progressivo e mortalidade infantil.")
                    c1, c2 = st.columns(2)
                    with c1:
                        custom_beta = st.number_input(
                            "β — forma",
                            min_value=0.1, max_value=10.0,
                            value=CUSTOM_BETA_DEFAULT, step=0.1,
                            help="β < 1: mortalidade infantil  |  β = 1: aleatório  |  β > 1: desgaste",
                        )
                    with c2:
                        custom_eta = st.number_input(
                            "η — escala (h)",
                            min_value=10.0, max_value=50000.0,
                            value=CUSTOM_ETA_DEFAULT, step=100.0,
                            help="63,2% dos equipamentos falharam até η horas.",
                        )
                else:  # Lognormal
                    st.caption("Lognormal — adequada para fadiga, corrosão e componentes eletrônicos.")
                    c1, c2 = st.columns(2)
                    with c1:
                        custom_mu = st.number_input(
                            "μ — log-média",
                            min_value=1.0, max_value=12.0,
                            value=CUSTOM_MU_DEFAULT, step=0.1,
                            help="Logaritmo natural da mediana de vida. μ=6,5 → mediana ≈ 665 h.",
                        )
                    with c2:
                        custom_sigma = st.number_input(
                            "σ — log-desvio",
                            min_value=0.05, max_value=3.0,
                            value=CUSTOM_SIGMA_DEFAULT, step=0.05,
                            help="Dispersão em escala log. Valores altos = alta variabilidade entre falhas.",
                        )
                    # Mostra mediana e percentis para orientar o usuário
                    import math
                    mediana = math.exp(custom_mu)
                    p10 = math.exp(custom_mu - 1.28 * custom_sigma)
                    p90 = math.exp(custom_mu + 1.28 * custom_sigma)
                    st.caption(
                        f"Mediana ≈ **{mediana:.0f} h** | P10 ≈ {p10:.0f} h | P90 ≈ {p90:.0f} h"
                    )

            if not tipo_eq:
                tipo_eq = "Equipamento Personalizado"
        else:
            tipo_eq = tipo_sel

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
            return _render_simulator(meta, tipo_eq, custom_beta, custom_eta, custom_mu, custom_sigma, custom_dist)
        elif mode == "Simulação Enriquecida (ISO 14224)":
            return _render_rich_simulator(meta, tipo_eq, tag_eq, custom_beta, custom_eta, custom_mu, custom_sigma, custom_dist)
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
    meta: Dict[str, Any], tipo_eq: str,
    custom_beta:  Optional[float] = None,
    custom_eta:   Optional[float] = None,
    custom_mu:    Optional[float] = None,
    custom_sigma: Optional[float] = None,
    custom_dist:  Optional[str]   = None,
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, None]:
    n = st.slider("Número de Amostras", 100, 2000, 500, 50)

    noise   = st.slider("Ruído Gaussiano (%)",     0.0, 50.0,  0.0, 1.0)
    outlier = st.slider("Mortalidade Infantil (%)", 0.0, 20.0,  0.0, 1.0)
    aging   = st.slider("Fadiga Sistêmica (%)",     0.0,  5.0,  0.0, 0.1)
    st.divider()

    _render_thresholds()

    if st.button("▶ Executar Simulação", type="primary", use_container_width=True):
        with st.spinner("Gerando dados simulados..."):
            records = api.simulate(
                int(n), tipo_eq, noise, outlier, aging,
                custom_beta=custom_beta, custom_eta=custom_eta,
                custom_mu=custom_mu, custom_sigma=custom_sigma,
                custom_dist=custom_dist,
            )
        st.success(f"✅ {len(records)} registros gerados.")
        return meta, records, True, None

    return meta, None, False, None


# ─── Simulador enriquecido ────────────────────────────────────────────────────

def _render_rich_simulator(
    meta: Dict[str, Any], tipo_eq: str, tag_eq: str,
    custom_beta:  Optional[float] = None,
    custom_eta:   Optional[float] = None,
    custom_mu:    Optional[float] = None,
    custom_sigma: Optional[float] = None,
    custom_dist:  Optional[str]   = None,
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, Optional[pd.DataFrame]]:

    st.caption("Gera dataset completo: modo de falha, causa raiz, TTR, datas, custo e produção perdida.")

    n = st.slider("Número de Amostras", 100, 2000, 500, 50, key="rich_n")

    noise   = st.slider("Ruído Gaussiano (%)",     0.0, 50.0,  0.0, 1.0, key="rich_noise")
    outlier = st.slider("Mortalidade Infantil (%)", 0.0, 20.0,  0.0, 1.0, key="rich_out")
    aging   = st.slider("Fadiga Sistêmica (%)",     0.0,  5.0,  0.0, 0.1, key="rich_aging")
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
                custom_beta=custom_beta,
                custom_eta=custom_eta,
                custom_mu=custom_mu,
                custom_sigma=custom_sigma,
                custom_dist=custom_dist,
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

    with st.expander("📋 Formato esperado do CSV", expanded=False):
        st.markdown("""
**O arquivo CSV deve conter pelo menos 2 colunas:**

| Coluna | Descrição | Exemplo |
|---|---|---|
| **Tempo (TBF)** | Tempo Entre Falhas em horas | `850.5` |
| **Status** | `1` = falha confirmada, `0` = censura (ainda operando) | `1` |

**Requisitos:**
- Mínimo de **100 registros**
- Separador: vírgula `,` ou ponto e vírgula `;`
- Sem linhas vazias no meio
- Valores numéricos (sem texto nas colunas de tempo/status)

**Exemplo de arquivo válido:**
```
TBF_horas,status
1200,1
850,1
1100,0
950,1
```
        """)

    file = st.file_uploader("Selecionar arquivo CSV", type=["csv"])
    if file is None:
        return meta, None, False, None

    file_bytes = file.read()

    try:
        with st.spinner("Lendo colunas..."):
            info = api.get_csv_columns(file_bytes, file.name)
    except Exception as e:
        st.error(f"❌ Erro ao ler o arquivo: {str(e)}\n\nVerifique se o arquivo é um CSV válido.")
        return meta, None, False, None

    cols   = info.get("columns", [])
    n_rows = info.get("n_rows", 0)
    st.caption(f"Arquivo: {n_rows} linhas × {len(cols)} colunas detectadas")

    if n_rows < 100:
        st.error(f"❌ Arquivo com apenas {n_rows} registros. Mínimo necessário: 100 registros para análise confiável.")
        return meta, None, False, None

    if len(cols) < 2:
        st.error("❌ O arquivo precisa ter pelo menos 2 colunas: Tempo (TBF) e Status.")
        return meta, None, False, None

    st.info(f"✅ Arquivo válido. Mapeie as colunas abaixo:")
    t_col = st.selectbox("Coluna de Tempo (TBF — horas)", cols,
                         help="Selecione a coluna que contém o tempo entre falhas em horas")
    s_col = st.selectbox("Coluna de Status (Falha=1 / Censura=0)", cols,
                         help="Selecione a coluna com 1 para falha confirmada e 0 para equipamento ainda operando")

    if t_col == s_col:
        st.warning("⚠️ As colunas de Tempo e Status não podem ser a mesma.")
        return meta, None, False, None

    _render_thresholds()

    if st.button("▶ Processar Dados Reais", type="primary", use_container_width=True):
        try:
            with st.spinner("Processando CSV..."):
                records = api.upload_csv(file_bytes, file.name, t_col, s_col)
            if not records:
                st.error("❌ Nenhum registro válido encontrado. Verifique se as colunas mapeadas contêm valores numéricos.")
                return meta, None, False, None
            st.success(f"✅ {len(records)} registros processados com sucesso.")
            return meta, records, True, None
        except Exception as e:
            st.error(f"❌ Erro ao processar: {str(e)}\n\nVerifique se os valores nas colunas selecionadas são numéricos.")
            return meta, None, False, None

    return meta, None, False, None
