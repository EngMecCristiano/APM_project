"""
Gerador de Dados Sintéticos Enriquecidos — APM Analytics.
Simula uma base completa com taxonomia ISO 14224:2016, datas, TTR,
contexto operacional, boundary classification e indicadores financeiros.

Equipamentos e cenários de falha são carregados do catálogo JSON (equipment_catalog.json),
tornando o sistema independente de setor industrial.

Colunas geradas (26):
  Identificação   : OS_Numero, Tag_Ativo, Tipo_Equipamento, Num_Evento
  Temporal        : Data_Inicio_Intervalo, Data_Evento, Data_Retorno_Operacao
  Confiabilidade  : TBF, TTR, Horimetro_Inicio, Horimetro_Evento, Falha
  Taxonomia       : Subcomponente, Modo_Falha, Causa_Raiz,
                    Mecanismo_Degradacao, Tipo_Manutencao, Criticidade, Boundary
  Operacional     : Carga_Media_Pct, Temperatura_Media_C, Toneladas_Processadas
  Financeiro      : Custo_Reparo_BRL, Impacto_Producao_t, Lucro_Cessante_BRL
  Acumulado       : Tempo_Acumulado, Disponibilidade_Ciclo_Pct
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from scipy.stats import weibull_min

from backend.config.settings import (
    EQUIPMENT_CATALOG, EQUIPMENT_PROFILES, DEFAULT_PROFILE
)


def _get_equipment_entry(equipment_type: str) -> Optional[Dict]:
    for eq in EQUIPMENT_CATALOG.get("equipment", []):
        if eq["name"] == equipment_type:
            return eq
    return None


def _get_failure_scenarios(equipment_type: str) -> List[Dict]:
    entry = _get_equipment_entry(equipment_type)
    if entry and entry.get("failure_scenarios"):
        return entry["failure_scenarios"]
    return EQUIPMENT_CATALOG.get("default_failure_scenarios", [
        {
            "subcomponente": "Componente Rotativo", "modo_falha": "Desgaste Mecânico",
            "causa_raiz": "Uso Normal / Fim de Vida", "mecanismo": "Abrasão",
            "criticidade": "Média", "boundary": "Interno",
            "ttr_mu": 2.5, "ttr_sigma": 0.5, "cost_factor": 1.0, "prob": 0.35,
        },
        {
            "subcomponente": "Sistema de Vedação", "modo_falha": "Falha de Vedação",
            "causa_raiz": "Envelhecimento / Desgaste", "mecanismo": "Fadiga",
            "criticidade": "Média", "boundary": "Interno",
            "ttr_mu": 2.0, "ttr_sigma": 0.4, "cost_factor": 1.2, "prob": 0.30,
        },
        {
            "subcomponente": "Mancal", "modo_falha": "Superaquecimento",
            "causa_raiz": "Lubrificação Deficiente", "mecanismo": "Fadiga Térmica",
            "criticidade": "Alta", "boundary": "Interno",
            "ttr_mu": 3.0, "ttr_sigma": 0.5, "cost_factor": 2.0, "prob": 0.35,
        },
    ])


def _get_operational_context(equipment_type: str) -> Dict:
    entry = _get_equipment_entry(equipment_type)
    if entry and entry.get("operational_context"):
        return entry["operational_context"]
    return EQUIPMENT_CATALOG.get("default_operational_context", {
        "throughput_t_per_h": 100.0, "temp_base_C": 45.0, "temp_std_C": 10.0,
        "load_mean_pct": 75.0, "load_std_pct": 12.0,
        "cost_per_ttr_h_brl": 5000.0, "preco_producao_brl_t": 50.0,
    })


class RichSyntheticGenerator:
    """
    Gera DataFrame enriquecido de eventos de manutenção para qualquer
    equipamento registrado no catálogo ISO 14224.
    """

    @staticmethod
    def generate(
        n_samples: int,
        equipment_type: str,
        noise_pct: float,
        outlier_pct: float,
        aging_pct: float,
        tag_ativo: str = "EQP-01A",
        start_date: str = "2021-01-01",
        preco_produto_brl_t: float = 45.0,
        custom_beta:  float | None = None,
        custom_eta:   float | None = None,
        custom_mu:    float | None = None,
        custom_sigma: float | None = None,
        custom_dist:  str   | None = None,
    ) -> pd.DataFrame:
        from scipy.stats import lognorm as lognorm_dist
        rng = np.random.default_rng(42)

        profile = EQUIPMENT_PROFILES.get(equipment_type, DEFAULT_PROFILE)
        if custom_beta is not None:
            profile = {**profile, "beta": custom_beta}
        if custom_eta is not None:
            profile = {**profile, "eta": custom_eta}
        beta, eta = profile["beta"], profile["eta"]

        ctx       = _get_operational_context(equipment_type)
        scenarios = _get_failure_scenarios(equipment_type)

        probs = np.array([s["prob"] for s in scenarios])
        probs /= probs.sum()

        # ── 1. Gerar TBF ───────────────────────────────────────────────────
        if custom_dist == "Lognormal" and custom_mu is not None and custom_sigma is not None:
            eta_ref  = np.exp(custom_mu)
            tbf_base = lognorm_dist.rvs(s=custom_sigma, scale=eta_ref,
                                        size=n_samples,
                                        random_state=int(rng.integers(1e6)))
        else:
            eta_ref  = eta
            tbf_base = weibull_min.rvs(beta, scale=eta, size=n_samples,
                                       random_state=int(rng.integers(1e6)))

        noise_arr = rng.normal(0.0, eta_ref * noise_pct / 100.0, size=n_samples)
        tbf_noisy = tbf_base + noise_arr

        # Mortalidade infantil
        n_out = int(n_samples * outlier_pct / 100.0)
        infant_idx: set = set()
        if n_out > 0:
            infant_idx_arr = rng.choice(n_samples, n_out, replace=False)
            tbf_noisy[infant_idx_arr] = rng.exponential(eta_ref * 0.08, size=n_out)
            infant_idx = set(infant_idx_arr.tolist())

        # Fadiga sistêmica
        normalized_pos = np.arange(n_samples) / max(n_samples - 1, 1)
        aging_arr = np.exp(-(aging_pct / 100.0) * np.power(normalized_pos, 1.5))
        tbf = np.maximum(np.round(tbf_noisy * aging_arr / 10.0) * 10.0, 2.0)

        # Censura: 15%
        falha = rng.choice([0, 1], size=n_samples, p=[0.15, 0.85])

        # ── 2. Cenários de falha ────────────────────────────────────────────
        scenario_idx = rng.choice(len(scenarios), size=n_samples, p=probs)

        # Mortalidade infantil → cenários de sobrecarga/acumulação se disponíveis
        overload_candidates = [
            i for i, s in enumerate(scenarios)
            if s.get("mecanismo", "") in (
                "Sobrecarga Mecânica", "Acumulação", "Contaminação",
                "Vibração Excessiva",
            )
        ]
        if overload_candidates:
            for idx in infant_idx:
                scenario_idx[idx] = rng.choice(overload_candidates)

        # ── 3. TTR ─────────────────────────────────────────────────────────
        ttr = np.zeros(n_samples)
        for i in range(n_samples):
            if falha[i] == 1:
                sc = scenarios[scenario_idx[i]]
                ttr[i] = max(
                    1.0,
                    np.round(
                        rng.lognormal(mean=sc["ttr_mu"], sigma=sc["ttr_sigma"]), 1
                    )
                )

        # ── 4. Datas e horímetro ────────────────────────────────────────────
        t0 = datetime.strptime(start_date, "%Y-%m-%d")
        horimetro_inicio = 0.0

        data_inicio, data_evento, data_retorno = [], [], []
        horimetro_ini, horimetro_evt = [], []

        current_dt = t0
        for i in range(n_samples):
            data_inicio.append(current_dt.strftime("%Y-%m-%d %H:%M"))
            horimetro_ini.append(horimetro_inicio)

            dt_evento = current_dt + timedelta(hours=float(tbf[i]))
            data_evento.append(dt_evento.strftime("%Y-%m-%d %H:%M"))
            horimetro_evt.append(horimetro_inicio + tbf[i])

            if falha[i] == 1:
                dt_retorno = dt_evento + timedelta(hours=float(ttr[i]))
                data_retorno.append(dt_retorno.strftime("%Y-%m-%d %H:%M"))
                current_dt = dt_retorno
            else:
                data_retorno.append("")
                current_dt = dt_evento

            horimetro_inicio = horimetro_evt[-1]

        # ── 5. Contexto operacional ─────────────────────────────────────────
        load_pct = np.clip(
            rng.normal(ctx["load_mean_pct"], ctx["load_std_pct"], size=n_samples),
            20.0, 100.0
        )
        temp_c = np.clip(
            rng.normal(ctx["temp_base_C"], ctx["temp_std_C"], size=n_samples)
            + (load_pct - ctx["load_mean_pct"]) * 0.3,
            ctx["temp_base_C"] - 20, ctx["temp_base_C"] + 35,
        )
        throughput_base = ctx["throughput_t_per_h"]
        tons = np.round(
            tbf * throughput_base * (load_pct / 100.0) * aging_arr, 0
        )

        # ── 6. Financeiro ───────────────────────────────────────────────────
        custo_reparo = np.zeros(n_samples)
        impacto_t    = np.zeros(n_samples)
        lucro_cess   = np.zeros(n_samples)

        cost_base = ctx["cost_per_ttr_h_brl"]
        preco_t   = preco_produto_brl_t or ctx["preco_producao_brl_t"]

        for i in range(n_samples):
            if falha[i] == 1:
                sc = scenarios[scenario_idx[i]]
                custo_reparo[i] = round(
                    ttr[i] * cost_base * sc["cost_factor"] * rng.uniform(0.85, 1.20),
                    -2
                )
                impacto_t[i] = round(ttr[i] * throughput_base * (load_pct[i] / 100.0), 0)
                lucro_cess[i] = round(impacto_t[i] * preco_t, -2)

        # ── 7. Tipo de manutenção e OS ──────────────────────────────────────
        _CENSURA_TIPOS  = ["Preventiva", "Parada Operacional", "Preditiva",
                           "Fim de Observação", "Transferência", "Censura"]
        _CENSURA_PROBS  = [0.38,          0.28,               0.20,
                           0.07,           0.04,              0.03]
        tipo_manut = []
        for i in range(n_samples):
            if falha[i] == 0:
                tipo_manut.append(rng.choice(_CENSURA_TIPOS, p=_CENSURA_PROBS))
            elif i in infant_idx:
                tipo_manut.append("Corretiva Emergencial")
            elif scenarios[scenario_idx[i]]["criticidade"] == "Alta":
                tipo_manut.append("Corretiva")
            else:
                tipo_manut.append(
                    rng.choice(["Corretiva", "Preventiva", "Preditiva"], p=[0.55, 0.30, 0.15])
                )

        os_nums = [
            f"OS-{(t0 + timedelta(hours=float(np.cumsum(tbf)[i]))).strftime('%Y')}-{i+1:04d}"
            for i in range(n_samples)
        ]

        # ── 8. Montar DataFrame ─────────────────────────────────────────────
        cum_tbf = np.cumsum(tbf)
        disp_ciclo = np.where(
            falha == 1,
            np.round(tbf / (tbf + ttr + 1e-9) * 100, 1),
            100.0,
        )

        rows = []
        for i in range(n_samples):
            sc = scenarios[scenario_idx[i]]
            boundary = sc.get("boundary", "Interno") if falha[i] == 1 else "—"
            row = {
                # Identificação
                "OS_Numero":               os_nums[i],
                "Tag_Ativo":               tag_ativo,
                "Tipo_Equipamento":        equipment_type,
                "Num_Evento":              i + 1,
                # Temporal
                "Data_Inicio_Intervalo":   data_inicio[i],
                "Data_Evento":             data_evento[i],
                "Data_Retorno_Operacao":   data_retorno[i],
                # Confiabilidade
                "TBF":                     float(tbf[i]),
                "TTR":                     float(ttr[i]),
                "Horimetro_Inicio":        float(horimetro_ini[i]),
                "Horimetro_Evento":        float(horimetro_evt[i]),
                "Falha":                   int(falha[i]),
                # Taxonomia ISO 14224
                "Subcomponente":           sc["subcomponente"] if falha[i] == 1 else "—",
                "Modo_Falha":              sc["modo_falha"]    if falha[i] == 1 else "Censura (Em Operação)",
                "Causa_Raiz":              sc["causa_raiz"]    if falha[i] == 1 else "—",
                "Mecanismo_Degradacao":    sc["mecanismo"]     if falha[i] == 1 else "—",
                "Tipo_Manutencao":         tipo_manut[i],
                "Criticidade":             sc["criticidade"]   if falha[i] == 1 else "—",
                "Boundary":                boundary,
                # Contexto operacional
                "Carga_Media_Pct":         float(round(load_pct[i], 1)),
                "Temperatura_Media_C":     float(round(temp_c[i], 1)),
                "Toneladas_Processadas":   float(tons[i]),
                # Financeiro
                "Custo_Reparo_BRL":        float(custo_reparo[i]),
                "Impacto_Producao_t":      float(impacto_t[i]),
                "Lucro_Cessante_BRL":      float(lucro_cess[i]),
                # Acumulado
                "Tempo_Acumulado":         float(cum_tbf[i]),
                "Disponibilidade_Ciclo_Pct": float(disp_ciclo[i]),
            }
            rows.append(row)

        return pd.DataFrame(rows)
