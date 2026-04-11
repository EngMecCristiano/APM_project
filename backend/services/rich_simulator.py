"""
Gerador de Dados Sintéticos Enriquecidos — APM Mining Analytics.
Simula uma base completa com taxonomia ISO 14224, datas, TTR,
contexto operacional e indicadores financeiros.

Colunas geradas (25):
  Identificação   : OS_Numero, Tag_Ativo, Tipo_Equipamento, Num_Evento
  Temporal        : Data_Inicio_Intervalo, Data_Evento, Data_Retorno_Operacao
  Confiabilidade  : TBF, TTR, Horimetro_Inicio, Horimetro_Evento, Falha
  Taxonomia       : Subcomponente, Modo_Falha, Causa_Raiz,
                    Mecanismo_Degradacao, Tipo_Manutencao, Criticidade
  Operacional     : Carga_Media_Pct, Temperatura_Media_C, Toneladas_Processadas
  Financeiro      : Custo_Reparo_BRL, Impacto_Producao_t, Lucro_Cessante_BRL
  Acumulado       : Tempo_Acumulado, Disponibilidade_Ciclo_Pct
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

from scipy.stats import weibull_min

from backend.config.settings import EQUIPMENT_PROFILES, DEFAULT_PROFILE

# ─── Taxonomia de Falhas por Equipamento (ISO 14224) ─────────────────────────
# Cada cenário: subcomponente, modo_falha, causa_raiz, mecanismo, criticidade,
#               ttr_mu (LogNormal), ttr_sigma, cost_factor (× custo_base),
#               prob (peso amostral)

FAILURE_SCENARIOS: Dict[str, List[Dict[str, Any]]] = {
    "Britador Cônico": [
        {
            "subcomponente": "Manto/Côncavo",
            "modo_falha":    "Desgaste Excessivo",
            "causa_raiz":    "Abrasividade do Minério",
            "mecanismo":     "Abrasão",
            "criticidade":   "Alta",
            "ttr_mu": 3.2, "ttr_sigma": 0.5, "cost_factor": 2.5,
            "prob": 0.28,
        },
        {
            "subcomponente": "Mancal Principal",
            "modo_falha":    "Superaquecimento",
            "causa_raiz":    "Contaminação do Lubrificante",
            "mecanismo":     "Fadiga Térmica",
            "criticidade":   "Alta",
            "ttr_mu": 3.0, "ttr_sigma": 0.4, "cost_factor": 3.0,
            "prob": 0.15,
        },
        {
            "subcomponente": "Pinhão/Coroa",
            "modo_falha":    "Fratura",
            "causa_raiz":    "Fadiga de Material",
            "mecanismo":     "Fadiga de Contato",
            "criticidade":   "Alta",
            "ttr_mu": 4.0, "ttr_sigma": 0.6, "cost_factor": 4.0,
            "prob": 0.10,
        },
        {
            "subcomponente": "Excêntrico",
            "modo_falha":    "Folga Excessiva",
            "causa_raiz":    "Desgaste Natural",
            "mecanismo":     "Abrasão",
            "criticidade":   "Média",
            "ttr_mu": 2.5, "ttr_sigma": 0.4, "cost_factor": 1.5,
            "prob": 0.12,
        },
        {
            "subcomponente": "Vedação Hidráulica",
            "modo_falha":    "Vazamento de Óleo",
            "causa_raiz":    "Envelhecimento da Vedação",
            "mecanismo":     "Fadiga",
            "criticidade":   "Média",
            "ttr_mu": 2.0, "ttr_sigma": 0.5, "cost_factor": 1.0,
            "prob": 0.10,
        },
        {
            "subcomponente": "Câmara de Britagem",
            "modo_falha":    "Bloqueio",
            "causa_raiz":    "Fragmento Metálico (Tramp Iron)",
            "mecanismo":     "Sobrecarga Mecânica",
            "criticidade":   "Alta",
            "ttr_mu": 2.2, "ttr_sigma": 0.4, "cost_factor": 1.2,
            "prob": 0.10,
        },
        {
            "subcomponente": "Eixo Vertical",
            "modo_falha":    "Fratura",
            "causa_raiz":    "Alimentação Desequilibrada",
            "mecanismo":     "Fadiga por Flexão",
            "criticidade":   "Alta",
            "ttr_mu": 4.5, "ttr_sigma": 0.5, "cost_factor": 5.0,
            "prob": 0.07,
        },
        {
            "subcomponente": "Sistema de Lubrificação",
            "modo_falha":    "Falha de Circulação",
            "causa_raiz":    "Entupimento do Filtro",
            "mecanismo":     "Contaminação",
            "criticidade":   "Média",
            "ttr_mu": 1.8, "ttr_sigma": 0.4, "cost_factor": 0.8,
            "prob": 0.08,
        },
    ],

    "Peneira Vibratória": [
        {
            "subcomponente": "Deck/Tela",
            "modo_falha":    "Ruptura de Tela",
            "causa_raiz":    "Fadiga por Vibração",
            "mecanismo":     "Fadiga",
            "criticidade":   "Alta",
            "ttr_mu": 2.5, "ttr_sigma": 0.5, "cost_factor": 1.5,
            "prob": 0.32,
        },
        {
            "subcomponente": "Molas de Isolamento",
            "modo_falha":    "Quebra de Mola",
            "causa_raiz":    "Fadiga de Material",
            "mecanismo":     "Fadiga",
            "criticidade":   "Alta",
            "ttr_mu": 2.0, "ttr_sigma": 0.4, "cost_factor": 1.2,
            "prob": 0.20,
        },
        {
            "subcomponente": "Mancal Vibratório",
            "modo_falha":    "Superaquecimento",
            "causa_raiz":    "Falha de Lubrificação",
            "mecanismo":     "Fadiga Térmica",
            "criticidade":   "Alta",
            "ttr_mu": 3.0, "ttr_sigma": 0.4, "cost_factor": 2.5,
            "prob": 0.15,
        },
        {
            "subcomponente": "Estrutura Metálica",
            "modo_falha":    "Trinca Estrutural",
            "causa_raiz":    "Fadiga por Vibração Ressonante",
            "mecanismo":     "Fadiga",
            "criticidade":   "Alta",
            "ttr_mu": 3.5, "ttr_sigma": 0.5, "cost_factor": 3.0,
            "prob": 0.10,
        },
        {
            "subcomponente": "Tensionador de Tela",
            "modo_falha":    "Folga de Fixação",
            "causa_raiz":    "Afrouxamento por Vibração",
            "mecanismo":     "Desgaste",
            "criticidade":   "Baixa",
            "ttr_mu": 1.5, "ttr_sigma": 0.3, "cost_factor": 0.5,
            "prob": 0.13,
        },
        {
            "subcomponente": "Excitador Vibratório",
            "modo_falha":    "Vibração Irregular",
            "causa_raiz":    "Desequilíbrio de Massas",
            "mecanismo":     "Desgaste",
            "criticidade":   "Média",
            "ttr_mu": 2.0, "ttr_sigma": 0.5, "cost_factor": 1.0,
            "prob": 0.10,
        },
    ],

    "Bomba de Polpa": [
        {
            "subcomponente": "Impeller/Rotor",
            "modo_falha":    "Erosão Excessiva",
            "causa_raiz":    "Abrasividade da Polpa",
            "mecanismo":     "Erosão-Corrosão",
            "criticidade":   "Alta",
            "ttr_mu": 2.8, "ttr_sigma": 0.5, "cost_factor": 2.0,
            "prob": 0.28,
        },
        {
            "subcomponente": "Vedação Mecânica",
            "modo_falha":    "Falha de Vedação",
            "causa_raiz":    "Desgaste Natural / pH Ácido",
            "mecanismo":     "Corrosão-Abrasão",
            "criticidade":   "Alta",
            "ttr_mu": 2.2, "ttr_sigma": 0.4, "cost_factor": 1.5,
            "prob": 0.22,
        },
        {
            "subcomponente": "Liner/Voluta",
            "modo_falha":    "Desgaste de Liner",
            "causa_raiz":    "Concentração de Sólidos Alta",
            "mecanismo":     "Abrasão",
            "criticidade":   "Média",
            "ttr_mu": 2.5, "ttr_sigma": 0.4, "cost_factor": 1.5,
            "prob": 0.18,
        },
        {
            "subcomponente": "Caixa de Sucção",
            "modo_falha":    "Cavitação",
            "causa_raiz":    "NPSH Insuficiente",
            "mecanismo":     "Cavitação",
            "criticidade":   "Alta",
            "ttr_mu": 3.2, "ttr_sigma": 0.5, "cost_factor": 2.5,
            "prob": 0.12,
        },
        {
            "subcomponente": "Duto de Sucção",
            "modo_falha":    "Entupimento",
            "causa_raiz":    "Partícula Acima do D_max do Projeto",
            "mecanismo":     "Acumulação",
            "criticidade":   "Média",
            "ttr_mu": 1.5, "ttr_sigma": 0.3, "cost_factor": 0.5,
            "prob": 0.10,
        },
        {
            "subcomponente": "Mancal",
            "modo_falha":    "Superaquecimento",
            "causa_raiz":    "Desalinhamento / Lubrificação Deficiente",
            "mecanismo":     "Fadiga Térmica",
            "criticidade":   "Alta",
            "ttr_mu": 3.0, "ttr_sigma": 0.4, "cost_factor": 2.0,
            "prob": 0.10,
        },
    ],

    "Transportador de Correia": [
        {
            "subcomponente": "Correia",
            "modo_falha":    "Rasgamento Longitudinal",
            "causa_raiz":    "Material Cortante no Produto",
            "mecanismo":     "Penetração/Corte",
            "criticidade":   "Alta",
            "ttr_mu": 3.5, "ttr_sigma": 0.5, "cost_factor": 3.0,
            "prob": 0.22,
        },
        {
            "subcomponente": "Rolo de Carga/Retorno",
            "modo_falha":    "Quebra de Rolo",
            "causa_raiz":    "Desgaste Natural / Acúmulo de Finos",
            "mecanismo":     "Fadiga-Abrasão",
            "criticidade":   "Média",
            "ttr_mu": 1.5, "ttr_sigma": 0.4, "cost_factor": 0.6,
            "prob": 0.22,
        },
        {
            "subcomponente": "Correia",
            "modo_falha":    "Desalinhamento de Correia",
            "causa_raiz":    "Carregamento Assimétrico",
            "mecanismo":     "Deformação",
            "criticidade":   "Média",
            "ttr_mu": 1.5, "ttr_sigma": 0.3, "cost_factor": 0.5,
            "prob": 0.16,
        },
        {
            "subcomponente": "Raspador",
            "modo_falha":    "Desgaste de Raspador",
            "causa_raiz":    "Abrasividade do Material",
            "mecanismo":     "Abrasão",
            "criticidade":   "Baixa",
            "ttr_mu": 1.2, "ttr_sigma": 0.3, "cost_factor": 0.4,
            "prob": 0.13,
        },
        {
            "subcomponente": "Redutor de Velocidade",
            "modo_falha":    "Falha de Engrenagem",
            "causa_raiz":    "Sobrecarga / Lubrificação Deficiente",
            "mecanismo":     "Fadiga de Contato",
            "criticidade":   "Alta",
            "ttr_mu": 4.0, "ttr_sigma": 0.5, "cost_factor": 4.0,
            "prob": 0.10,
        },
        {
            "subcomponente": "Tambor de Acionamento",
            "modo_falha":    "Desgaste do Revestimento",
            "causa_raiz":    "Deslizamento da Correia",
            "mecanismo":     "Abrasão",
            "criticidade":   "Alta",
            "ttr_mu": 3.0, "ttr_sigma": 0.5, "cost_factor": 2.0,
            "prob": 0.10,
        },
        {
            "subcomponente": "Mancal de Tambor",
            "modo_falha":    "Superaquecimento",
            "causa_raiz":    "Lubrificação Deficiente",
            "mecanismo":     "Fadiga Térmica",
            "criticidade":   "Média",
            "ttr_mu": 2.2, "ttr_sigma": 0.4, "cost_factor": 1.2,
            "prob": 0.07,
        },
    ],
}

# ─── Contexto Operacional por Equipamento ──────────────────────────────────────

OPERATIONAL_CONTEXT: Dict[str, Dict[str, float]] = {
    "Britador Cônico": {
        "throughput_t_per_h":    250.0,   # t/h em operação
        "temp_base_C":            55.0,
        "temp_std_C":             10.0,
        "load_mean_pct":          78.0,
        "load_std_pct":           12.0,
        "cost_per_ttr_h_brl":   8500.0,  # custo de manutenção por h de reparo
        "preco_producao_brl_t":   45.0,  # valor do minério perdido
    },
    "Peneira Vibratória": {
        "throughput_t_per_h":    350.0,
        "temp_base_C":            42.0,
        "temp_std_C":              7.0,
        "load_mean_pct":          72.0,
        "load_std_pct":           10.0,
        "cost_per_ttr_h_brl":   4200.0,
        "preco_producao_brl_t":   45.0,
    },
    "Bomba de Polpa": {
        "throughput_t_per_h":    120.0,
        "temp_base_C":            48.0,
        "temp_std_C":             12.0,
        "load_mean_pct":          82.0,
        "load_std_pct":           10.0,
        "cost_per_ttr_h_brl":   5500.0,
        "preco_producao_brl_t":   45.0,
    },
    "Transportador de Correia": {
        "throughput_t_per_h":    600.0,
        "temp_base_C":            35.0,
        "temp_std_C":              8.0,
        "load_mean_pct":          70.0,
        "load_std_pct":           12.0,
        "cost_per_ttr_h_brl":   3800.0,
        "preco_producao_brl_t":   45.0,
    },
}


class RichSyntheticGenerator:
    """
    Gera DataFrame enriquecido de eventos de manutenção para equipamentos de mineração.
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
        custom_beta: float | None = None,
        custom_eta:  float | None = None,
    ) -> pd.DataFrame:
        rng = np.random.default_rng(42)

        profile = EQUIPMENT_PROFILES.get(equipment_type, DEFAULT_PROFILE)
        if custom_beta is not None:
            profile = {**profile, "beta": custom_beta}
        if custom_eta is not None:
            profile = {**profile, "eta": custom_eta}
        beta, eta = profile["beta"], profile["eta"]
        ctx = OPERATIONAL_CONTEXT.get(equipment_type, list(OPERATIONAL_CONTEXT.values())[0])
        scenarios = FAILURE_SCENARIOS.get(equipment_type, FAILURE_SCENARIOS["Britador Cônico"])
        probs = np.array([s["prob"] for s in scenarios])
        probs /= probs.sum()

        # ── 1. Gerar TBF (mesma lógica do simulador base) ──────────────────
        tbf_base = weibull_min.rvs(beta, scale=eta, size=n_samples,
                                   random_state=int(rng.integers(1e6)))
        noise_arr = rng.normal(0.0, eta * noise_pct / 100.0, size=n_samples)
        tbf_noisy = tbf_base + noise_arr

        # Mortalidade infantil (outliers de curta duração)
        n_out = int(n_samples * outlier_pct / 100.0)
        infant_idx = set()
        if n_out > 0:
            infant_idx_arr = rng.choice(n_samples, n_out, replace=False)
            tbf_noisy[infant_idx_arr] = rng.exponential(eta * 0.08, size=n_out)
            infant_idx = set(infant_idx_arr.tolist())

        # Fadiga sistêmica (degradação progressiva do TBF)
        k = (aging_pct / 100.0) / (n_samples * 0.5)
        aging_arr = np.exp(-k * np.power(np.arange(n_samples), 1.5))
        tbf = np.maximum(np.round(tbf_noisy * aging_arr / 10.0) * 10.0, 2.0)

        # Censura: 15% dos registros
        falha = rng.choice([0, 1], size=n_samples, p=[0.15, 0.85])

        # ── 2. Cenários de falha ────────────────────────────────────────────
        scenario_idx = rng.choice(len(scenarios), size=n_samples, p=probs)

        # Mortalidade infantil → puxar cenário com mecanismo de sobrecarga/bloqueio
        # (cenário de maior custo_factor é indicativo de falha catastrófica)
        overload_candidates = [
            i for i, s in enumerate(scenarios)
            if s["mecanismo"] in ("Sobrecarga Mecânica", "Acumulação", "Contaminação")
        ]
        if overload_candidates:
            for idx in infant_idx:
                scenario_idx[idx] = rng.choice(overload_candidates)

        # ── 3. TTR (Time To Repair) ─────────────────────────────────────────
        ttr = np.zeros(n_samples)
        for i in range(n_samples):
            if falha[i] == 1:
                sc = scenarios[scenario_idx[i]]
                ttr[i] = max(
                    1.0,
                    np.round(
                        rng.lognormal(mean=sc["ttr_mu"], sigma=sc["ttr_sigma"]),
                        1
                    )
                )
            # Censura: TTR = 0 (sem reparo, apenas fim de observação)

        # ── 4. Datas e horímetro ────────────────────────────────────────────
        t0 = datetime.strptime(start_date, "%Y-%m-%d")
        horimetro_inicio = 0.0

        data_inicio   = []
        data_evento   = []
        data_retorno  = []
        horimetro_ini = []
        horimetro_evt = []

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
                data_retorno.append("")          # censura: sem data de retorno
                current_dt = dt_evento

            horimetro_inicio = horimetro_evt[-1]

        # ── 5. Contexto operacional ─────────────────────────────────────────
        load_pct  = np.clip(
            rng.normal(ctx["load_mean_pct"], ctx["load_std_pct"], size=n_samples),
            20.0, 100.0
        )
        temp_c = np.clip(
            rng.normal(ctx["temp_base_C"], ctx["temp_std_C"], size=n_samples) +
            (load_pct - ctx["load_mean_pct"]) * 0.3,
            ctx["temp_base_C"] - 20, ctx["temp_base_C"] + 35
        )
        # Throughput diminui com envelhecimento e carga abaixo do nominal
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
                # Custo de reparo = TTR × custo_base × fator do cenário + variação
                custo_reparo[i] = round(
                    ttr[i] * cost_base * sc["cost_factor"] *
                    rng.uniform(0.85, 1.20),
                    -2  # arredonda às centenas
                )
                impacto_t[i] = round(ttr[i] * throughput_base * (load_pct[i] / 100.0), 0)
                lucro_cess[i] = round(impacto_t[i] * preco_t, -2)

        # ── 7. Tipo de manutenção e OS ──────────────────────────────────────
        tipo_manut = []
        for i in range(n_samples):
            if falha[i] == 0:
                tipo_manut.append("Censura")
            elif i in infant_idx:
                tipo_manut.append("Corretiva Emergencial")
            elif scenarios[scenario_idx[i]]["criticidade"] == "Alta":
                tipo_manut.append("Corretiva")
            else:
                tipo_manut.append(
                    rng.choice(
                        ["Corretiva", "Preventiva", "Preditiva"],
                        p=[0.55, 0.30, 0.15]
                    )
                )

        os_nums = [f"OS-{(t0 + timedelta(hours=float(np.cumsum(tbf)[i]))).strftime('%Y')}-{i+1:04d}"
                   for i in range(n_samples)]

        # ── 8. Montar DataFrame ─────────────────────────────────────────────
        cum_tbf = np.cumsum(tbf)
        disp_ciclo = np.where(
            falha == 1,
            np.round(tbf / (tbf + ttr + 1e-9) * 100, 1),
            100.0
        )

        rows = []
        for i in range(n_samples):
            sc = scenarios[scenario_idx[i]]
            row = {
                # Identificação
                "OS_Numero":            os_nums[i],
                "Tag_Ativo":            tag_ativo,
                "Tipo_Equipamento":     equipment_type,
                "Num_Evento":           i + 1,
                # Temporal
                "Data_Inicio_Intervalo":  data_inicio[i],
                "Data_Evento":            data_evento[i],
                "Data_Retorno_Operacao":  data_retorno[i],
                # Confiabilidade
                "TBF":                  float(tbf[i]),
                "TTR":                  float(ttr[i]),
                "Horimetro_Inicio":     float(horimetro_ini[i]),
                "Horimetro_Evento":     float(horimetro_evt[i]),
                "Falha":                int(falha[i]),
                # Taxonomia ISO 14224
                "Subcomponente":        sc["subcomponente"] if falha[i] == 1 else "—",
                "Modo_Falha":           sc["modo_falha"]    if falha[i] == 1 else "Censura (Em Operação)",
                "Causa_Raiz":           sc["causa_raiz"]    if falha[i] == 1 else "—",
                "Mecanismo_Degradacao": sc["mecanismo"]     if falha[i] == 1 else "—",
                "Tipo_Manutencao":      tipo_manut[i],
                "Criticidade":          sc["criticidade"]   if falha[i] == 1 else "—",
                # Contexto operacional
                "Carga_Media_Pct":      float(round(load_pct[i], 1)),
                "Temperatura_Media_C":  float(round(temp_c[i], 1)),
                "Toneladas_Processadas": float(tons[i]),
                # Financeiro
                "Custo_Reparo_BRL":     float(custo_reparo[i]),
                "Impacto_Producao_t":   float(impacto_t[i]),
                "Lucro_Cessante_BRL":   float(lucro_cess[i]),
                # Acumulado
                "Tempo_Acumulado":      float(cum_tbf[i]),
                "Disponibilidade_Ciclo_Pct": float(disp_ciclo[i]),
            }
            rows.append(row)

        return pd.DataFrame(rows)
