"""
Serviço de Otimização de Manutenção Preventiva.
Modelo de Substituição por Idade (Age-Based Replacement Policy) — Teoria da Renovação.

C(tp) = [Cp·R(tp) + Cu·F(tp)] / ∫₀^tp R(x)dx

Válido para β > 1 (regime de desgaste — mineração).
"""
from __future__ import annotations

import numpy as np
from scipy.integrate import quad
from scipy.optimize import minimize_scalar
from scipy.stats import weibull_min
from scipy.special import gamma as gamma_fn

from backend.config.settings import PMO_T_RANGE_LOW, PMO_T_RANGE_HIGH, PMO_CURVE_POINTS
from backend.schemas.models import PMORequest, PMOResult


class MaintenanceOptimizer:

    @staticmethod
    def compute(req: PMORequest) -> PMOResult:
        beta = req.beta
        eta  = req.eta
        cp   = req.custo_preventivo
        cu   = req.custo_corretivo

        def taxa_custo(tp: float) -> float:
            if tp <= 0:
                return 1e10
            r_tp = weibull_min.sf(tp, beta, scale=eta)
            f_tp = 1.0 - r_tp
            ciclo, _ = quad(lambda x: weibull_min.sf(x, beta, scale=eta), 0.0, tp)
            if ciclo < 1e-9:
                return 1e10
            return (cp * r_tp + cu * f_tp) / ciclo

        resultado = minimize_scalar(
            taxa_custo,
            bounds=(eta * PMO_T_RANGE_LOW, eta * PMO_T_RANGE_HIGH),
            method="bounded",
        )
        tp_otimo = float(resultado.x)
        disponibilidade  = float(weibull_min.sf(tp_otimo, beta, scale=eta))
        custo_na_otimo   = taxa_custo(tp_otimo)

        # Política puramente corretiva: Cu / MTTF (MTTF = η × Γ(1+1/β))
        mttf = eta * gamma_fn(1.0 + 1.0 / beta)
        custo_corr_puro  = cu / mttf
        reducao_custo    = max(0.0, (custo_corr_puro - custo_na_otimo) / custo_corr_puro * 100)

        t_range    = np.linspace(eta * PMO_T_RANGE_LOW, eta * 2.5, PMO_CURVE_POINTS)
        custo_curva = np.array([taxa_custo(t) for t in t_range])

        return PMOResult(
            tp_otimo=tp_otimo,
            disponibilidade=disponibilidade,
            reducao_custo_pct=reducao_custo,
            custo_na_otimo=float(custo_na_otimo),
            custo_corretivo_puro=float(custo_corr_puro),
            t_range=t_range.tolist(),
            custo_curva=custo_curva.tolist(),
        )
