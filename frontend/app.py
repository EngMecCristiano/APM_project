"""
APM Analytics — Frontend Streamlit (cliente fino).
Orquestra chamadas ao backend FastAPI e renderiza os componentes visuais.
Toda a computação matemática vive no backend; o frontend cuida apenas da UI.
"""
from __future__ import annotations

import sys
import os
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="APM Analytics Terminal",
    page_icon="⚙️",
    layout="wide",
)

import frontend.api_client as api
from frontend.styles.theme import build_css
from frontend.components.dashboard import (
    display_header, display_health_battery, display_kpi_cards, display_asset_info,
)
from frontend.components.sidebar import render_sidebar
from frontend.components.tabs import lda_tab, rul_tab, nhpp_tab, ml_tab, audit_tab
from frontend.components.ui_helpers import kpi_row, html_table
from frontend.api_client import BackendError

BG_PATH = Path(__file__).parent.parent / "images" / "apm_app_background.png"
st.markdown(build_css(BG_PATH), unsafe_allow_html=True)


# ─── Estado da sessão ────────────────────────────────────────────────────────

def _init_state() -> None:
    for key in ("records", "meta", "fit", "rul", "ca", "audit", "ml", "rich_df", "history_records"):
        if key not in st.session_state:
            st.session_state[key] = None
    if "rul_threshold" not in st.session_state:
        st.session_state["rul_threshold"] = 0.10
    if "risk_thresholds" not in st.session_state:
        st.session_state["risk_thresholds"] = None


# ─── Verificação de backend ───────────────────────────────────────────────────

def _check_backend() -> bool:
    try:
        return api.health_check()
    except Exception:
        return False


# ─── Aba de Dados Enriquecidos ────────────────────────────────────────────────

def _render_rich_tab(df: pd.DataFrame) -> None:
    """Exibe o dataset enriquecido com filtros, estatísticas e download."""

    # ── KPIs de topo ─────────────────────────────────────────────────────────
    falhas = df[df["Falha"] == 1]
    kpi_row([
        ("Total de Eventos",   str(len(df)),                                           "registros"),
        ("Falhas Registradas", str(len(falhas)),                                       "status = 1"),
        ("Custo Total Reparo", f"R$ {falhas['Custo_Reparo_BRL'].sum():,.0f}",         "acumulado"),
        ("Produção Perdida",   f"{falhas['Impacto_Producao_t'].sum():,.0f} t",        "paradas"),
        ("Lucro Cessante",     f"R$ {falhas['Lucro_Cessante_BRL'].sum():,.0f}",       "impacto total"),
    ])

    st.divider()

    # ── Filtros ───────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        modos = ["Todos"] + sorted(falhas["Modo_Falha"].unique().tolist())
        modo_sel = st.selectbox("Filtrar por Modo de Falha", modos)
    with col_f2:
        crit_opts = ["Todos", "Alta", "Média", "Baixa"]
        crit_sel = st.selectbox("Criticidade", crit_opts)
    with col_f3:
        tipo_opts = ["Todos"] + sorted(df["Tipo_Manutencao"].unique().tolist())
        tipo_sel = st.selectbox("Tipo de Manutenção", tipo_opts)

    df_view = df.copy()
    if modo_sel != "Todos":
        df_view = df_view[df_view["Modo_Falha"] == modo_sel]
    if crit_sel != "Todos":
        df_view = df_view[df_view["Criticidade"] == crit_sel]
    if tipo_sel != "Todos":
        df_view = df_view[df_view["Tipo_Manutencao"] == tipo_sel]

    st.caption(f"Exibindo {len(df_view)} de {len(df)} registros")
    html_table(df_view, max_rows=300)

    # ── Distribuições de falha ────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Modos de Falha")
        mc = (falhas["Modo_Falha"].value_counts().reset_index())
        mc.columns = ["Modo de Falha", "Qtd"]
        html_table(mc)

    with col_b:
        st.markdown("#### Causa Raiz")
        cc = (falhas["Causa_Raiz"].value_counts().reset_index())
        cc.columns = ["Causa Raiz", "Qtd"]
        html_table(cc)

    # ── Subcomponente × Custo ─────────────────────────────────────────────────
    st.markdown("#### Custo por Subcomponente")
    custo_sub = (
        falhas.groupby("Subcomponente")
        .agg(Qtd=("Falha", "count"), Custo_Total_BRL=("Custo_Reparo_BRL", "sum"),
             TTR_Medio_h=("TTR", "mean"))
        .sort_values("Custo_Total_BRL", ascending=False)
        .reset_index()
    )
    custo_sub["Custo_Total_BRL"] = custo_sub["Custo_Total_BRL"].map("R$ {:,.0f}".format)
    custo_sub["TTR_Medio_h"]     = custo_sub["TTR_Medio_h"].map("{:.1f} h".format)
    html_table(custo_sub)

    st.divider()

    # ── Download CSV ──────────────────────────────────────────────────────────
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ Baixar Dataset Completo (CSV)",
        data=csv_bytes,
        file_name=f"apm_dataset_enriquecido_{df['Tag_Ativo'].iloc[0]}.csv",
        mime="text/csv",
    )


# ─── Orquestrador principal ───────────────────────────────────────────────────

def main() -> None:
    _init_state()

    meta, records, triggered, rich_df = render_sidebar()

    if triggered and records:
        # ── Mesclar histórico acumulado (se usuário optou por incluir) ────────
        hist_records = st.session_state.get("history_records") or []
        if hist_records:
            # Deduplica por Tempo_Acumulado — o histórico pode ter sobreposição
            seen = {r["Tempo_Acumulado"] for r in records}
            extra = [r for r in hist_records if r["Tempo_Acumulado"] not in seen]
            combined = extra + records          # histórico primeiro (mais antigo)
            st.toast(f"📂 Histórico: +{len(extra)} registros anteriores incluídos na análise.")
        else:
            combined = records

        st.session_state.records  = combined
        st.session_state.meta     = meta
        st.session_state.rich_df  = rich_df  # None se não for simulação enriquecida

        _analysis_ok = True

        try:
            with st.spinner("Ajustando modelos paramétricos..."):
                st.session_state.fit = api.fit_models(combined)
        except BackendError as e:
            st.error(f"❌ Falha no ajuste de modelos: {e.detail}")
            _analysis_ok = False
        except Exception as e:
            st.error(f"❌ Erro inesperado no ajuste: {e}")
            _analysis_ok = False

        if _analysis_ok:
            fit  = st.session_state.fit
            best = fit["best"]

            try:
                with st.spinner("Calculando RUL..."):
                    st.session_state.rul = api.compute_rul(
                        dist_params=best,
                        current_age=meta["horimetro_atual"],
                        rul_threshold=st.session_state.get("rul_threshold", 0.10),
                        n_bootstrap=st.session_state.get("n_bootstrap", 300),
                    )
            except BackendError as e:
                st.error(f"❌ Falha no cálculo do RUL: {e.detail}")
                _analysis_ok = False
            except Exception as e:
                st.error(f"❌ Erro inesperado no RUL: {e}")
                _analysis_ok = False

        if _analysis_ok:
            try:
                with st.spinner("Processando Crow-AMSAA (MLE)..."):
                    st.session_state.ca = api.crow_amsaa(combined)
            except BackendError as e:
                st.error(f"❌ Falha na análise Crow-AMSAA: {e.detail}")
            except Exception as e:
                st.error(f"❌ Erro inesperado no Crow-AMSAA: {e}")

            try:
                with st.spinner("Gerando auditoria estatística..."):
                    st.session_state.audit = api.audit(
                        records=combined,
                        dist_params=best,
                        horimetro_atual=meta["horimetro_atual"],
                    )
            except BackendError as e:
                st.error(f"❌ Falha na auditoria: {e.detail}")
            except Exception as e:
                st.error(f"❌ Erro inesperado na auditoria: {e}")

            try:
                with st.spinner("Treinando modelos ML..."):
                    st.session_state.ml = api.ml_analyze(
                        records=combined,
                        horimetro_atual=meta["horimetro_atual"],
                        rul_data=st.session_state.rul,
                        weibull_params=best,
                        risk_thresholds=st.session_state.get("risk_thresholds"),
                    )
            except BackendError as e:
                st.error(f"❌ Falha na análise ML: {e.detail}")
            except Exception as e:
                st.error(f"❌ Erro inesperado no ML: {e}")

            # ── Persistir sessão no histórico do ativo ────────────────────────
            try:
                saved = api.history_save(
                    tag=meta["tag"],
                    records=records,   # salva apenas os novos (sem o histórico já persistido)
                    meta=meta,
                )
                total = saved.get("total_registros", len(records))
                st.toast(f"💾 Histórico salvo — {total} registros acumulados para {meta['tag']}.")
            except Exception:
                pass  # falha silenciosa — não interrompe a análise

    if st.session_state.records is None:
        display_header(meta or {})
        st.markdown(
            '<div style="background:rgba(234,179,8,0.12);border:1px solid rgba(234,179,8,0.45);'
            'border-radius:8px;padding:10px 14px;color:#FDE68A;font-size:14px;font-weight:500;">'
            '👈 Configure os parâmetros na barra lateral e clique em <strong>Executar</strong> para iniciar.'
            '</div>',
            unsafe_allow_html=True,
        )
        if not _check_backend():
            st.error(
                "⚠️ Backend não está acessível. "
                f"Verifique se o serviço FastAPI está em `{os.getenv('BACKEND_URL', 'http://localhost:8002')}`"
            )
        return

    records  = st.session_state.records
    meta     = st.session_state.meta
    fit      = st.session_state.fit
    rul      = st.session_state.rul
    ca       = st.session_state.ca
    audit    = st.session_state.audit
    ml       = st.session_state.ml
    rich_df  = st.session_state.rich_df

    if fit is None or rul is None:
        st.warning("⚠️ Análise incompleta — verifique os erros acima e tente novamente.")
        return

    best = fit["best"]

    health_score    = int(rul["r_current"] * 100)
    reliability_pct = health_score
    risk_level = (
        "HIGH"   if rul["rul_time"] < 500  else
        "MEDIUM" if rul["rul_time"] < 1000 else
        "LOW"
    )

    display_header(meta)

    col_bat, col_kpis = st.columns([1, 3])
    with col_kpis:
        display_kpi_cards(risk_level, reliability_pct, meta["horimetro_atual"], audit)
    with col_bat:
        display_health_battery(health_score)

    display_asset_info(meta)

    # ── Abas — inclui aba de dados enriquecidos quando disponível ─────────────
    tab_labels = [
        "📊 Dados de Vida — LDA",
        "🔮 Preditiva — RUL",
        "📈 Degradação — RGA/NHPP",
        "🧠 Machine Learning",
        "🧮 EDA + Auditoria",
    ]
    if rich_df is not None:
        tab_labels.append("🗃️ Dataset ISO 14224")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        lda_tab.render(records, fit, meta)
    with tabs[1]:
        rul_tab.render(rul, fit, meta,
                       rul_threshold=st.session_state.get("rul_threshold", 0.10))
    with tabs[2]:
        if ca is not None:
            nhpp_tab.render(ca, meta)
        else:
            st.info("Crow-AMSAA não disponível — verifique erros acima.")
    with tabs[3]:
        if ml is not None:
            ml_tab.render(ml, fit, rul, records, meta)
        else:
            st.info("Análise ML não disponível — verifique erros acima.")
    with tabs[4]:
        if audit is not None:
            audit_tab.render(audit, records, meta)
        else:
            st.info("Auditoria não disponível — verifique erros acima.")

    if rich_df is not None:
        with tabs[5]:
            _render_rich_tab(rich_df)

    # ── Exportação PDF ────────────────────────────────────────────────────────
    _render_pdf_export(meta, fit, rul, ca or {}, audit or {}, ml or {})


def _render_pdf_export(
    meta: dict, fit: dict, rul: dict, ca: dict, audit: dict, ml: dict
) -> None:
    """Botão de download do relatório PDF — aparece no rodapé da página."""
    st.divider()
    col_pdf, col_info = st.columns([1, 3])
    with col_pdf:
        if st.button("📄 Gerar Relatório PDF", use_container_width=True):
            try:
                with st.spinner("Gerando PDF..."):
                    pdf_bytes = api.generate_pdf(
                        meta=meta, fit=fit, rul=rul,
                        ca=ca, audit=audit, ml=ml,
                    )
                tag      = meta.get("tag", "ativo").replace(" ", "_")
                filename = f"APM_Relatorio_{tag}.pdf"
                st.download_button(
                    label="⬇️ Baixar PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True,
                )
            except BackendError as e:
                st.error(f"❌ Falha na geração do PDF: {e.detail}")
            except Exception as e:
                st.error(f"❌ Erro inesperado: {e}")
    with col_info:
        st.caption(
            "O relatório PDF inclui: identificação do ativo, saúde e RUL com IC Bootstrap, "
            "modelos paramétricos (ranking AICc), Crow-AMSAA, ML preditivo e auditoria estatística."
        )


if __name__ == "__main__":
    main()
