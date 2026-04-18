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

# ─── Listas ISO 14224 estáticas (espelham equipment_catalog.json) ─────────────
ENVIRONMENTAL_CLASSIFICATIONS = [
    "Ambiente Geral",
    "Área Classificada (Zona 1)",
    "Área Classificada (Zona 2)",
    "Offshore — Plataforma",
    "Offshore — FPSO",
    "Onshore — Deserto",
    "Onshore — Tropical",
    "Onshore — Ártico",
    "Ambiente Corrosivo",
    "Sala Limpa",
]

MECANISMOS_DEGRADACAO = [
    "Abrasão", "Erosão", "Corrosão", "Fadiga", "Fadiga Térmica",
    "Fadiga de Contato", "Fadiga por Flexão", "Fadiga por Torção",
    "Erosão-Corrosão", "Corrosão-Abrasão", "Fadiga-Abrasão",
    "Cavitação", "Desgaste", "Deformação Plástica", "Fratura Frágil",
    "Penetração/Corte", "Sobrecarga Mecânica", "Acumulação",
    "Contaminação", "Degradação Elétrica", "Degradação Térmica",
    "Vibração Excessiva", "Desequilíbrio",
]

CAUSAS_PARADA = [
    "Corretiva", "Corretiva Emergencial",       # falha real → Falha = 1
    "Preventiva", "Preditiva",                  # intervenção planejada → Falha = 0
    "Parada Operacional",                        # processo parou → Falha = 0
    "Fim de Observação",                         # último registro do período → Falha = 0
    "Transferência",                             # equipamento relocado → Falha = 0
    "Geral",                                     # censura genérica → Falha = 0
]
CRITICIDADES     = ["Alta", "Média", "Baixa"]
BOUNDARIES       = ["Interno", "Externo"]


@st.cache_data(ttl=300)
def _fetch_catalog() -> List[Dict]:
    """Carrega catálogo de equipamentos do backend com cache de 5 min."""
    try:
        return api.get_equipment_catalog()
    except Exception:
        return []


def _build_equipment_options(catalog: List[Dict]) -> Tuple[List[str], Dict[str, str]]:
    """
    Retorna lista de nomes para o selectbox e mapa nome→setor.
    Agrupa por setor com separadores visuais.
    """
    by_sector: Dict[str, List[str]] = {}
    sector_map: Dict[str, str] = {}
    for eq in catalog:
        s = eq.get("sector", "Geral")
        by_sector.setdefault(s, []).append(eq["name"])
        sector_map[eq["name"]] = s

    options: List[str] = []
    for sector, names in by_sector.items():
        options.append(f"── {sector} ──")   # separador de grupo (não selecionável)
        options.extend(names)
    return options, sector_map


def render_sidebar() -> Tuple[
    Optional[Dict[str, Any]],
    Optional[List[Dict]],
    bool,
    Optional[pd.DataFrame],
]:
    """
    Renderiza a sidebar e retorna (meta, records, triggered, rich_df).
    - records: lista slim {TBF, Tempo_Acumulado, Falha} para o pipeline de análise
    - rich_df: DataFrame completo (26 col) apenas quando modo Enriquecido
    """
    with st.sidebar:
        st.markdown(
            '<p style="font-size:17px;font-weight:700;color:#DEF7FF;margin:0 0 4px 0;'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            '⚙️ Configuração do Estudo</p>',
            unsafe_allow_html=True,
        )

        # ── Fluxo de trabalho ─────────────────────────────────────────────────
        with st.expander("📋 Fluxo de Trabalho", expanded=False):
            st.markdown("""
**Análise de Confiabilidade**
1. Selecione o equipamento no catálogo ISO 14224
2. Preencha TAG, horímetro e metadados
3. Escolha o modo de entrada de dados
4. Importe ou insira os dados de falha
5. Clique em **Executar / Processar**
6. Navegue pelas abas de análise

**Manutenção Prescritiva com IA**
Após executar a análise completa:

7. Acesse a aba **Machine Learning**
8. Clique na sub-aba **🤖 Manutenção Prescritiva**
9. Clique em **Gerar Prescrição com IA**
10. O agente analisa risco, RUL e catálogo ISO 14224 e entrega
    um plano de ação priorizado com janelas de intervenção

> Para resultados mais precisos na prescrição: use **Importar CSV Real**
> com dados históricos reais e selecione o equipamento correto no catálogo.
""")

        st.divider()

        # ── Seleção de equipamento (catálogo ISO 14224 dinâmico) ─────────────
        catalog = _fetch_catalog()
        options, sector_map = _build_equipment_options(catalog)

        def _is_separator(opt: str) -> bool:
            return opt.startswith("──")

        selected = st.selectbox(
            "Classe do Ativo",
            options=options,
            format_func=lambda x: x,
        )

        # Se separador foi selecionado, força para o primeiro item válido
        if _is_separator(selected):
            valid = [o for o in options if not _is_separator(o)]
            selected = valid[0] if valid else ""
            st.session_state["_sidebar_eq"] = selected

        tipo_eq  = selected
        setor_eq = sector_map.get(selected, "Geral")

        eq_info = next((e for e in catalog if e["name"] == selected), None)
        if eq_info:
            st.caption(
                f"**{eq_info.get('iso14224_class', '')}** · {setor_eq} · "
                f"β={eq_info['beta']:.1f} · η={eq_info['eta']:.0f} h · "
                f"{eq_info['n_scenarios']} cenários de falha"
            )

        # ── Identificação do ativo ────────────────────────────────────────────
        tag_eq   = st.text_input("TAG Operacional", value="EQP-01A")
        serie_eq = st.text_input("Número de Série", value="SN-000000",
                                 help="Identificador único para rastreabilidade.")
        h_atual  = st.number_input("Horímetro Atual (h)", value=800.0, step=100.0)

        # ── Metadados ISO 14224 ───────────────────────────────────────────────
        with st.expander("📋 Metadados ISO 14224", expanded=False):
            st.caption("Campos de identificação conforme ISO 14224:2016 §6.3.")
            fabricante = st.text_input("Fabricante", value="",
                                       placeholder="ex: SKF, Sulzer, Siemens")
            modelo = st.text_input("Modelo / Referência", value="",
                                   placeholder="ex: LT110, MBH-300")
            data_inst = st.text_input("Data de Instalação", value="",
                                      placeholder="AAAA-MM-DD")
            class_amb = st.selectbox(
                "Classificação Ambiental",
                options=ENVIRONMENTAL_CLASSIFICATIONS,
                help="Ambiente operacional conforme ISO 14224 §5.4.",
            )
            responsavel = st.text_input("Responsável pela Manutenção", value="",
                                        placeholder="ex: Equipe Mecânica Turno A")

        meta: Dict[str, Any] = {
            "tag":                      tag_eq,
            "nome":                     "Equipamento",
            "numero_serie":             serie_eq,
            "tipo_equipamento":         tipo_eq,
            "horimetro_atual":          float(h_atual),
            "data_estudo":              datetime.now().strftime("%d/%m/%Y"),
            "fabricante":               fabricante or None,
            "modelo":                   modelo or None,
            "data_instalacao":          data_inst or None,
            "classificacao_ambiental":  class_amb,
            "setor":                    setor_eq,
            "responsavel_manutencao":   responsavel or None,
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
            [
                "Simulador Paramétrico",
                "Simulação Enriquecida (ISO 14224)",
                "Entrada Manual (ISO 14224)",
                "Importar CSV Real",
            ],
            label_visibility="collapsed",
        )
        st.divider()

        if mode == "Simulador Paramétrico":
            return _render_simulator(meta, tipo_eq)
        elif mode == "Simulação Enriquecida (ISO 14224)":
            return _render_rich_simulator(meta, tipo_eq, tag_eq)
        elif mode == "Entrada Manual (ISO 14224)":
            return _render_manual_entry(meta, tipo_eq, tag_eq, catalog)
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
                "MÉD ≥", min_value=5, max_value=60, value=30, step=5,
                help="Score ≥ este valor → risco MÉDIO.",
            )
        with c2:
            risk_alto = st.number_input(
                "ALTO ≥", min_value=risk_medio + 5, max_value=85,
                value=max(50, risk_medio + 5), step=5,
                help="Score ≥ este valor → risco ALTO.",
            )
        with c3:
            risk_critical = st.number_input(
                "CRIT ≥", min_value=risk_alto + 5, max_value=95,
                value=max(70, risk_alto + 5), step=5,
                help="Score ≥ este valor → risco CRÍTICO.",
            )

        n_bootstrap = st.select_slider(
            "Bootstrap RUL (amostras)",
            options=[50, 100, 200, 300, 500, 1000],
            value=300,
            help="Número de reamostragens para o IC do RUL.",
        )

        st.session_state["rul_threshold"]   = rul_pct / 100.0
        st.session_state["n_bootstrap"]     = int(n_bootstrap)
        st.session_state["risk_thresholds"] = {
            "critical": int(risk_critical),
            "alto":     int(risk_alto),
            "medio":    int(risk_medio),
        }


# ─── Simulador básico ─────────────────────────────────────────────────────────

def _render_simulator(
    meta: Dict[str, Any],
    tipo_eq: str,
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, None]:
    n       = st.slider("Número de Amostras", 100, 2000, 500, 50)
    noise   = st.slider("Ruído Gaussiano (%)",      0.0, 50.0, 0.0, 1.0)
    outlier = st.slider("Mortalidade Infantil (%)", 0.0, 20.0, 0.0, 1.0)
    aging   = st.slider("Fadiga Sistêmica (%)",     0.0,  5.0, 0.0, 0.1)
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
    meta: Dict[str, Any],
    tipo_eq: str,
    tag_eq: str,
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, Optional[pd.DataFrame]]:

    st.caption("Gera dataset completo: modo de falha, causa raiz, TTR, datas, custo, boundary e produção perdida.")

    n       = st.slider("Número de Amostras", 100, 2000, 500, 50, key="rich_n")
    noise   = st.slider("Ruído Gaussiano (%)",      0.0, 50.0, 0.0, 1.0, key="rich_noise")
    outlier = st.slider("Mortalidade Infantil (%)", 0.0, 20.0, 0.0, 1.0, key="rich_out")
    aging   = st.slider("Fadiga Sistêmica (%)",     0.0,  5.0, 0.0, 0.1, key="rich_aging")
    st.divider()

    start_date = st.date_input("Data de Início do Histórico", value=datetime(2021, 1, 1))
    preco_t    = st.number_input("Valor do Produto (R$/t)", value=45.0, step=5.0,
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
        records = [
            {"TBF": r["TBF"], "Tempo_Acumulado": r["Tempo_Acumulado"], "Falha": r["Falha"]}
            for r in raw
        ]

        n_boundary_ext = int((rich_df["Boundary"] == "Externo").sum()) if "Boundary" in rich_df.columns else 0
        st.success(
            f"✅ {len(records)} eventos | "
            f"{int(rich_df['Falha'].sum())} falhas | "
            f"{len(rich_df['Modo_Falha'].unique())} modos de falha | "
            f"{n_boundary_ext} causas externas (boundary)"
        )
        return meta, records, True, rich_df

    return meta, None, False, None


# ─── Entrada Manual ISO 14224 ────────────────────────────────────────────────

def _taxonomy_field(
    label: str,
    catalog_values: List[str],
    key: str,
    help_text: str = "",
) -> str:
    """
    Selectbox com valores do catálogo + opção 'Livre (personalizado)' que revela
    um text_input para o usuário digitar valor livre.
    """
    OPTIONS = catalog_values + ["Livre (personalizado)"]
    sel = st.selectbox(label, OPTIONS, key=f"{key}_sel", help=help_text)
    if sel == "Livre (personalizado)":
        val = st.text_input(f"▸ {label} personalizado", key=f"{key}_txt",
                            placeholder="Digite o valor...")
        return val.strip() or "—"
    return sel


def _render_manual_entry(
    meta: Dict[str, Any],
    tipo_eq: str,
    tag_eq: str,
    catalog: List[Dict],
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, None]:
    """
    Formulário de entrada manual de eventos de manutenção com taxonomia ISO 14224 completa.
    Os eventos são acumulados em session_state e salvos no banco como histórico rico.
    """
    st.caption("Registre eventos reais com taxonomia ISO 14224. Os dados são salvos no banco por TAG.")

    # Busca cenários do equipamento selecionado para popular dropdowns
    eq_entry  = next((e for e in catalog if e["name"] == tipo_eq), None)
    scenarios = eq_entry.get("failure_scenarios", []) if eq_entry else []

    # Se equipamento não encontrado no catálogo, agrega todos os cenários como referência
    if not scenarios:
        all_scenarios = [s for eq in catalog for s in eq.get("failure_scenarios", [])]
        scenarios = all_scenarios

    subcomps       = sorted({s["subcomponente"] for s in scenarios}) or ["—"]
    modos          = sorted({s["modo_falha"]    for s in scenarios}) or ["—"]
    causas         = sorted({s["causa_raiz"]    for s in scenarios}) or ["—"]
    mecanismos_cat = sorted({s["mecanismo"]     for s in scenarios}) or ["—"]

    mecanismos_all = MECANISMOS_DEGRADACAO or mecanismos_cat

    if "manual_events" not in st.session_state:
        st.session_state["manual_events"] = []

    # ── Formulário de novo evento ─────────────────────────────────────────────
    with st.expander("➕ Adicionar Evento de Manutenção", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            data_evt = st.date_input("Data do Evento", key="me_data_evt")
            tbf = st.number_input("TBF (horas)", min_value=0.1, value=100.0,
                                  step=10.0, key="me_tbf",
                                  help="Tempo Entre Falhas em horas.")
        with c2:
            falha = st.selectbox("Tipo de Registro", [1, 0], key="me_falha",
                                 format_func=lambda x: "1 — Falha Confirmada" if x == 1 else "0 — Censura (Em Operação)")
            ttr = st.number_input("TTR (horas)", min_value=0.0, value=0.0,
                                  step=1.0, key="me_ttr",
                                  help="Time To Repair. Zero para censuras.")

        os_num = st.text_input("Número da OS", value="",
                               placeholder="ex: OS-2024-0001 (auto se vazio)", key="me_os")

        st.markdown("**Taxonomia ISO 14224**")

        sub  = _taxonomy_field("Subcomponente", subcomps, "me_sub",
                               "Parte do equipamento onde ocorreu a falha.")
        modo = _taxonomy_field("Modo de Falha", modos, "me_modo",
                               "Como a falha se manifestou (ex: Desgaste, Fratura).")
        causa = _taxonomy_field("Causa Raiz", causas, "me_causa",
                                "Por que a falha ocorreu (ex: Lubrificação Deficiente).")
        mec  = _taxonomy_field("Mecanismo de Degradação", mecanismos_all, "me_mec",
                               "Processo físico-químico da degradação (ex: Fadiga, Corrosão).")

        c3, c4, c5 = st.columns(3)
        with c3:
            tipo_m = st.selectbox("Causa da Parada", CAUSAS_PARADA, key="me_tipo")
        with c4:
            crit = st.selectbox("Criticidade", CRITICIDADES, key="me_crit")
        with c5:
            bound = st.selectbox("Boundary", BOUNDARIES, key="me_bound",
                                 help="Interno: causa dentro do equipamento. Externo: causa no processo/ambiente.")

        st.markdown("**Contexto Operacional (opcional)**")
        c6, c7, c8 = st.columns(3)
        with c6:
            carga = st.number_input("Carga (%)", 0.0, 100.0, 75.0, 5.0, key="me_carga")
        with c7:
            temp = st.number_input("Temperatura (°C)", -50.0, 500.0, 45.0, 5.0, key="me_temp")
        with c8:
            tons = st.number_input("Toneladas Processadas", 0.0, 1e7, 0.0, 100.0, key="me_tons")

        st.markdown("**Financeiro (opcional)**")
        c9, c10 = st.columns(2)
        with c9:
            custo = st.number_input("Custo Reparo (R$)", 0.0, 1e8, 0.0, 100.0, key="me_custo")
        with c10:
            lucro = st.number_input("Lucro Cessante (R$)", 0.0, 1e9, 0.0, 100.0, key="me_lucro")

        _TIPOS_CENSURA_FRONT = {
            "Preventiva", "Preditiva",
            "Parada Operacional", "Fim de Observação", "Transferência",
            "Geral",
        }
        if tipo_m in _TIPOS_CENSURA_FRONT:
            st.info(f"ℹ️ **{tipo_m}** → registro tratado como **dado censurado** (Falha = 0).")

        if st.button("➕ Adicionar à Lista", use_container_width=True):
            # Qualquer tipo não-corretivo → sempre censura (Falha = 0)
            falha_efetivo = 0 if tipo_m in _TIPOS_CENSURA_FRONT else int(falha)
            n_evt    = len(st.session_state["manual_events"]) + 1
            tempo_ac = sum(e["TBF"] for e in st.session_state["manual_events"]) + tbf
            evento   = {
                "OS_Numero":               os_num or f"OS-{data_evt.strftime('%Y')}-{n_evt:04d}",
                "Tag_Ativo":               tag_eq,
                "Tipo_Equipamento":        tipo_eq,
                "Num_Evento":              n_evt,
                "Data_Inicio_Intervalo":   "",
                "Data_Evento":             data_evt.strftime("%d/%m/%Y"),
                "Data_Retorno_Operacao":   "",
                "TBF":                     float(tbf),
                "TTR":                     float(ttr),
                "Horimetro_Inicio":        0.0,
                "Horimetro_Evento":        tempo_ac,
                "Falha":                   falha_efetivo,
                "Subcomponente":           sub   if falha_efetivo == 1 else "—",
                "Modo_Falha":              modo  if falha_efetivo == 1 else "Censura (Em Operação)",
                "Causa_Raiz":              causa if falha_efetivo == 1 else "—",
                "Mecanismo_Degradacao":    mec   if falha_efetivo == 1 else "—",
                "Causa_Parada":            tipo_m,
                "Criticidade":             crit  if falha_efetivo == 1 else "—",
                "Boundary":                bound if falha_efetivo == 1 else "—",
                "Carga_Media_Pct":         float(carga),
                "Temperatura_Media_C":     float(temp),
                "Toneladas_Processadas":   float(tons),
                "Custo_Reparo_BRL":        float(custo),
                "Impacto_Producao_t":      0.0,
                "Lucro_Cessante_BRL":      float(lucro),
                "Tempo_Acumulado":         float(tempo_ac),
                "Disponibilidade_Ciclo_Pct": round(tbf / (tbf + ttr + 1e-9) * 100, 1) if falha_efetivo == 1 else 100.0,
            }
            st.session_state["manual_events"].append(evento)
            st.success(f"✅ Evento #{n_evt} adicionado. Total: {len(st.session_state['manual_events'])} eventos.")

    # ── Lista de eventos acumulados ───────────────────────────────────────────
    events = st.session_state["manual_events"]
    if events:
        st.markdown(f"**{len(events)} evento(s) na fila:**")
        preview_cols = ["Num_Evento", "Data_Evento", "TBF", "TTR", "Falha",
                        "Subcomponente", "Modo_Falha", "Criticidade", "Boundary"]
        df_preview = pd.DataFrame(events)[[c for c in preview_cols if c in pd.DataFrame(events).columns]]
        st.dataframe(df_preview, use_container_width=True, height=180)

        c_save, c_clear = st.columns(2)
        with c_save:
            if st.button("💾 Salvar na Base", type="primary", use_container_width=True):
                try:
                    with st.spinner("Salvando no banco..."):
                        res_rich = api.history_save_rich(tag_eq, events, meta)
                        slim = [{"TBF": e["TBF"], "Tempo_Acumulado": e["Tempo_Acumulado"],
                                 "Falha": e["Falha"]} for e in events]
                        api.history_save(tag_eq, slim, meta)
                    st.success(
                        f"✅ {res_rich.get('total_registros', len(events))} registros "
                        f"ISO 14224 salvos para TAG **{tag_eq}**."
                    )
                    st.session_state["manual_events"] = []
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao salvar: {e}")

        with c_clear:
            if st.button("🗑️ Limpar Lista", use_container_width=True):
                st.session_state["manual_events"] = []
                st.rerun()

        _render_thresholds()

        if st.button("▶ Analisar Dados Inseridos", use_container_width=True):
            slim = [{"TBF": e["TBF"], "Tempo_Acumulado": e["Tempo_Acumulado"],
                     "Falha": e["Falha"]} for e in events]
            return meta, slim, True, pd.DataFrame(events)
    else:
        st.info("Nenhum evento adicionado ainda. Preencha o formulário acima.")

    return meta, None, False, None


# ─── Upload CSV ───────────────────────────────────────────────────────────────

_RICH_COLS_REQUIRED = {"TBF", "Falha"}
_RICH_COLS_ALL = [
    "OS_Numero", "Tag_Ativo", "Tipo_Equipamento", "Num_Evento",
    "Data_Inicio_Intervalo", "Data_Evento", "Data_Retorno_Operacao",
    "TBF", "TTR", "Horimetro_Inicio", "Horimetro_Evento", "Falha",
    "Subcomponente", "Modo_Falha", "Causa_Raiz", "Mecanismo_Degradacao",
    "Causa_Parada", "Criticidade", "Boundary",
    "Carga_Media_Pct", "Temperatura_Media_C", "Toneladas_Processadas",
    "Custo_Reparo_BRL", "Impacto_Producao_t", "Lucro_Cessante_BRL",
    "Disponibilidade_Ciclo_Pct",
]


def _render_upload(
    meta: Dict[str, Any]
) -> Tuple[Optional[Dict], Optional[List[Dict]], bool, None]:

    fmt = st.radio(
        "Formato do CSV",
        ["Mínimo (TBF + Status)", "ISO 14224 Completo (26 colunas)"],
        horizontal=True,
        help="Mínimo: apenas tempo e status de falha. Completo: todas as colunas ISO 14224 — habilita aba Dataset e Manutenção Prescritiva enriquecida.",
    )

    if fmt == "Mínimo (TBF + Status)":
        with st.expander("📋 Como montar o CSV Mínimo", expanded=False):
            st.markdown("""
**Requisitos:** ≥ 100 registros · separador `,` ou `;` · sem linhas completamente vazias.

| Coluna | Tipo | Descrição |
|---|---|---|
| **TBF** (qualquer nome) | número | Tempo Entre Falhas em horas — ex: `850.5` |
| **Status** (qualquer nome) | inteiro | `1` = falha confirmada · `0` = censura (em operação) |

```csv
TBF_horas,status
1200,1
850,1
1100,0
950,1
720,1
```

> Você escolhe o nome das colunas na tela — o sistema faz o mapeamento automático.
> **Manutenção Preventiva** no campo de status deve ser `0` (dado censurado, não é falha).
""")
    else:
        with st.expander("📋 Como montar o CSV ISO 14224 Completo", expanded=False):
            st.markdown(f"""
**Colunas obrigatórias:** `TBF`, `Falha` — as demais são opcionais e preenchidas com padrão se ausentes.

| # | Coluna | Tipo | Descrição |
|---|---|---|---|
| 1 | `OS_Numero` | texto | Número da Ordem de Serviço — ex: `OS-2024-0001` |
| 2 | `Tag_Ativo` | texto | Identificação do ativo — ex: `BBA-101A` |
| 3 | `Tipo_Equipamento` | texto | Classe ISO 14224 — ex: `Centrifugal Pump` |
| 4 | `Num_Evento` | inteiro | Sequência do evento |
| 5 | `Data_Inicio_Intervalo` | data | Início do intervalo de operação — ex: `2023-01-15` |
| 6 | `Data_Evento` | data | Data da falha ou intervenção |
| 7 | `Data_Retorno_Operacao` | data | Data de retorno (vazio para censuras) |
| 8 | `TBF` ⚠️ | número | **Obrigatório** — Tempo Entre Falhas em horas |
| 9 | `TTR` | número | Tempo para Reparo em horas |
| 10 | `Horimetro_Inicio` | número | Horímetro no início do intervalo |
| 11 | `Horimetro_Evento` | número | Horímetro no momento do evento |
| 12 | `Falha` ⚠️ | inteiro | **Obrigatório** — `1` = falha · `0` = censura |
| 13 | `Subcomponente` | texto | Ex: `Rolamento`, `Selo Mecânico` |
| 14 | `Modo_Falha` | texto | Ex: `Desgaste`, `Fratura`, `Vazamento` |
| 15 | `Causa_Raiz` | texto | Ex: `Lubrificação Deficiente`, `Sobrecarga` |
| 16 | `Mecanismo_Degradacao` | texto | Ex: `Fadiga`, `Corrosão`, `Erosão` |
| 17 | `Causa_Parada` | texto | `Corretiva` · `Corretiva Emergencial` · `Preventiva` · `Preditiva` · `Parada Operacional` · `Fim de Observação` · `Transferência` · `Geral` |
| 18 | `Criticidade` | texto | `Alta` · `Média` · `Baixa` |
| 19 | `Boundary` | texto | `Interno` · `Externo` |
| 20 | `Carga_Media_Pct` | número | Carga operacional média em % |
| 21 | `Temperatura_Media_C` | número | Temperatura média em °C |
| 22 | `Toneladas_Processadas` | número | Volume processado no intervalo |
| 23 | `Custo_Reparo_BRL` | número | Custo de mão-de-obra + peças em R$ |
| 24 | `Impacto_Producao_t` | número | Toneladas perdidas pela parada |
| 25 | `Lucro_Cessante_BRL` | número | Receita não gerada pela parada em R$ |
| 26 | `Disponibilidade_Ciclo_Pct` | número | Disponibilidade do ciclo em % |

> **Regra de censura automática:** qualquer `Causa_Parada` não-corretiva força `Falha = 0`.
> Se a coluna estiver ausente, o sistema preenche automaticamente: `Falha=1 → Corretiva`, `Falha=0 → Geral`.
""")

    file = st.file_uploader("Selecionar arquivo CSV", type=["csv"])
    if file is None:
        return meta, None, False, None

    file_bytes = file.read()

    # ── Leitura de colunas ────────────────────────────────────────────────────
    try:
        with st.spinner("Lendo colunas..."):
            info = api.get_csv_columns(file_bytes, file.name)
    except Exception as e:
        st.error(f"❌ Erro ao ler o arquivo: {str(e)}\n\nVerifique se o arquivo é um CSV válido.")
        return meta, None, False, None

    cols   = info.get("columns", [])
    n_rows = info.get("n_rows", 0)
    st.caption(f"Arquivo: {n_rows} linhas × {len(cols)} colunas detectadas")

    if n_rows < 3:
        st.error(f"❌ Arquivo com apenas {n_rows} registros. Mínimo necessário: 3.")
        return meta, None, False, None

    # ── MODO MÍNIMO ───────────────────────────────────────────────────────────
    if fmt == "Mínimo (TBF + Status)":
        if n_rows < 100:
            st.warning(f"⚠️ Apenas {n_rows} registros — mínimo recomendado é 100 para análise robusta.")

        if len(cols) < 2:
            st.error("❌ O arquivo precisa ter pelo menos 2 colunas: Tempo e Status.")
            return meta, None, False, None

        st.info("✅ Arquivo válido. Mapeie as colunas abaixo:")
        t_col = st.selectbox("Coluna de Tempo (TBF — horas)", cols,
                             help="Coluna com o tempo entre falhas em horas")
        s_col = st.selectbox("Coluna de Status (Falha=1 / Censura=0)", cols,
                             help="1 = falha confirmada · 0 = equipamento em operação (censura)")

        if t_col == s_col:
            st.warning("⚠️ As colunas de Tempo e Status não podem ser a mesma.")
            return meta, None, False, None

        _render_thresholds()

        if st.button("▶ Processar Dados Reais", type="primary", use_container_width=True):
            try:
                with st.spinner("Processando CSV..."):
                    records = api.upload_csv(file_bytes, file.name, t_col, s_col)
                if not records:
                    st.error("❌ Nenhum registro válido encontrado.")
                    return meta, None, False, None
                st.success(f"✅ {len(records)} registros processados com sucesso.")
                return meta, records, True, None
            except Exception as e:
                st.error(f"❌ Erro ao processar: {str(e)}")
                return meta, None, False, None

    # ── MODO ISO 14224 COMPLETO ───────────────────────────────────────────────
    else:
        cols_set = set(cols)
        missing_required = _RICH_COLS_REQUIRED - cols_set
        if missing_required:
            st.error(f"❌ Colunas obrigatórias ausentes: {', '.join(sorted(missing_required))}")
            return meta, None, False, None

        cols_present = [c for c in _RICH_COLS_ALL if c in cols_set]
        cols_absent  = [c for c in _RICH_COLS_ALL if c not in cols_set]

        col_a, col_b = st.columns(2)
        with col_a:
            st.success(f"✅ {len(cols_present)}/26 colunas ISO 14224 detectadas")
        with col_b:
            if cols_absent:
                st.info(f"ℹ️ {len(cols_absent)} colunas ausentes — preenchidas com padrão")

        if cols_absent:
            with st.expander(f"Ver {len(cols_absent)} coluna(s) que serão preenchidas com padrão"):
                st.caption(" · ".join(cols_absent))

        # Validação ISO 14224 opcional
        if st.checkbox("Validar conformidade ISO 14224", value=True,
                       help="Verifica score de conformidade e lista problemas no CSV."):
            with st.spinner("Validando conformidade ISO 14224..."):
                try:
                    val = api.validate_iso14224(file_bytes, file.name)
                    score = val.get("score_conformidade", 0)
                    color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                    st.markdown(
                        f"**Score ISO 14224:** :{color}[{score:.0f}/100] — "
                        + ("✅ Conforme" if val.get("conforme") else "⚠️ Não conforme")
                    )
                    st.caption(val.get("resumo", ""))
                    issues = val.get("issues", [])
                    if issues:
                        with st.expander(f"Ver {len(issues)} issue(s) encontrada(s)"):
                            for iss in issues:
                                icon = "🔴" if iss["severidade"] == "erro" else "🟡"
                                loc  = f" (linha {iss['linha']})" if iss.get("linha") else ""
                                st.markdown(f"{icon} **{iss['campo']}**{loc}: {iss['descricao']}")
                except Exception as e:
                    st.warning(f"Não foi possível validar ISO 14224: {e}")

        _render_thresholds()

        if st.button("▶ Processar CSV ISO 14224", type="primary", use_container_width=True):
            try:
                with st.spinner("Processando CSV ISO 14224..."):
                    raw = api.upload_csv_rich(file_bytes, file.name)
                if not raw:
                    st.error("❌ Nenhum registro válido encontrado.")
                    return meta, None, False, None

                rich_df = pd.DataFrame(raw)
                records = [
                    {"TBF": r["TBF"], "Tempo_Acumulado": r["Tempo_Acumulado"], "Falha": r["Falha"]}
                    for r in raw
                ]
                n_falhas   = int(rich_df["Falha"].sum())
                n_censuras = len(rich_df) - n_falhas
                modos_uniq = rich_df["Modo_Falha"].nunique() if "Modo_Falha" in rich_df.columns else 0
                st.success(
                    f"✅ {len(records)} eventos | {n_falhas} falhas | {n_censuras} censuras"
                    + (f" | {modos_uniq} modos de falha" if modos_uniq else "")
                )
                return meta, records, True, rich_df
            except Exception as e:
                st.error(f"❌ Erro ao processar: {str(e)}")
                return meta, None, False, None

    return meta, None, False, None
