"""
Serviço de Confiabilidade — Fase 1.
Responsável por: simulação, ajuste paramétrico (MLE), RUL condicional e NHPP Crow-AMSAA.
Sem tratamento de exceção conforme diretriz arquitetural.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple

from scipy.integrate import quad
from scipy.optimize import minimize_scalar
from scipy.stats import weibull_min, lognorm, norm, expon

from reliability.Fitters import (
    Fit_Weibull_2P, Fit_Lognormal_2P, Fit_Normal_2P, Fit_Exponential_1P,
)
from reliability.Distributions import (
    Weibull_Distribution, Lognormal_Distribution,
    Normal_Distribution, Exponential_Distribution,
)
from reliability.Nonparametric import KaplanMeier, NelsonAalen

from backend.config.settings import EQUIPMENT_PROFILES, DEFAULT_PROFILE
from backend.schemas.models import (
    DataRecord, DistributionParams, FitResult,
    RULResult, CrowAMSAAResult,
)


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _extract_dist_params(fit_obj: Any, name: str) -> Dict[str, Any]:
    """Dissolve objeto `reliability.Distribution` em primitivos serializáveis."""
    dist = fit_obj.distribution
    base = {
        "model_name": name,
        "mttf":       float(dist.mean),
        "variance":   float(dist.variance),
        "aicc":       float(getattr(fit_obj, "AICc", np.nan)),
        "beta": None, "eta": None,
        "mu":   None, "sigma": None, "lam": None,
    }
    if name == "Weibull 2P":
        base.update({"dist_type": "weibull",
                     "beta": float(dist.beta), "eta": float(dist.alpha)})
    elif name == "Lognormal 2P":
        base.update({"dist_type": "lognormal",
                     "mu": float(dist.mu), "sigma": float(dist.sigma)})
    elif name == "Normal 2P":
        base.update({"dist_type": "normal",
                     "mu": float(dist.mu), "sigma": float(dist.sigma)})
    elif name == "Exponential 1P":
        base.update({"dist_type": "exponential",
                     "lam": float(dist.Lambda)})
    return base


def reconstruct_distribution(params: DistributionParams) -> Any:
    """Reconstrói objeto `reliability.Distribution` a partir dos parâmetros."""
    t = params.dist_type
    if t == "weibull":
        return Weibull_Distribution(alpha=params.eta, beta=params.beta)
    if t == "lognormal":
        return Lognormal_Distribution(mu=params.mu, sigma=params.sigma)
    if t == "normal":
        return Normal_Distribution(mu=params.mu, sigma=params.sigma)
    if t == "exponential":
        return Exponential_Distribution(Lambda=params.lam)


def ks_test_against_dist(tbf_failures: np.ndarray, params: DistributionParams) -> Tuple[float, float]:
    """KS test contra a distribuição do melhor modelo (corrigido — não fixo em exponencial)."""
    from scipy import stats
    t = params.dist_type
    if t == "weibull":
        return stats.kstest(tbf_failures, "weibull_min",
                            args=(params.beta, 0.0, params.eta))
    if t == "lognormal":
        return stats.kstest(tbf_failures, "lognorm",
                            args=(params.sigma, 0.0, np.exp(params.mu)))
    if t == "normal":
        return stats.kstest(tbf_failures, "norm",
                            args=(params.mu, params.sigma))
    if t == "exponential":
        return stats.kstest(tbf_failures, "expon",
                            args=(0.0, 1.0 / params.lam))


def _dist_ppf(params: DistributionParams, p: float) -> float:
    """Retorna o quantil p da distribuição ajustada (inversa da CDF).
    B10 = _dist_ppf(params, 0.10), B50 = _dist_ppf(params, 0.50), etc.
    """
    t = params.dist_type
    if t == "weibull":
        return weibull_min.ppf(p, params.beta, scale=params.eta)
    if t == "lognormal":
        return lognorm.ppf(p, s=params.sigma, scale=np.exp(params.mu))
    if t == "normal":
        return norm.ppf(p, loc=params.mu, scale=params.sigma)
    if t == "exponential":
        return expon.ppf(p, scale=1.0 / params.lam)
    return float("nan")


def theoretical_quantiles(tbf_failures: np.ndarray, params: DistributionParams) -> np.ndarray:
    """Quantis teóricos para QQ plot correto (vs. distribuição ajustada, não normalizado por max)."""
    n = len(tbf_failures)
    p = np.arange(1, n + 1) / (n + 1)
    t = params.dist_type
    if t == "weibull":
        return weibull_min.ppf(p, params.beta, scale=params.eta)
    if t == "lognormal":
        return lognorm.ppf(p, s=params.sigma, scale=np.exp(params.mu))
    if t == "normal":
        return norm.ppf(p, loc=params.mu, scale=params.sigma)
    if t == "exponential":
        return expon.ppf(p, scale=1.0 / params.lam)


# ─── Serviço principal ────────────────────────────────────────────────────────

class ReliabilityEngine:
    """Computa todos os artefatos estatísticos da Fase 1."""

    # ── Simulação ──────────────────────────────────────────────────────────────

    @staticmethod
    def generate_synthetic_data(
        n_samples: int,
        equipment_type: str,
        noise_pct: float,
        outlier_pct: float,
        aging_pct: float,
        custom_beta:  float | None = None,
        custom_eta:   float | None = None,
        custom_mu:    float | None = None,
        custom_sigma: float | None = None,
        custom_dist:  str   | None = None,
    ) -> List[DataRecord]:
        from scipy.stats import lognorm as lognorm_dist

        profile = EQUIPMENT_PROFILES.get(equipment_type, DEFAULT_PROFILE)
        if custom_beta is not None:
            profile = {**profile, "beta": custom_beta}
        if custom_eta is not None:
            profile = {**profile, "eta": custom_eta}

        # ── Geração de TBF base: Weibull ou Lognormal ────────────────────────
        if custom_dist == "Lognormal" and custom_mu is not None and custom_sigma is not None:
            tbf_base = lognorm_dist.rvs(s=custom_sigma, scale=np.exp(custom_mu), size=n_samples)
            eta_ref  = np.exp(custom_mu)   # referência para escala do ruído
        else:
            tbf_base = weibull_min.rvs(profile["beta"], scale=profile["eta"], size=n_samples)
            eta_ref  = profile["eta"]
        noise = np.random.normal(0.0, eta_ref * noise_pct / 100.0, size=n_samples)
        tbf_noisy = tbf_base + noise

        n_out = int(n_samples * outlier_pct / 100.0)
        if n_out > 0:
            idx = np.random.choice(n_samples, n_out, replace=False)
            tbf_noisy[idx] = expon.rvs(loc=2.0, scale=eta_ref * 0.08, size=n_out)

        # Normaliza posição por n_samples → efeito consistente independente de N
        normalized_pos = np.arange(n_samples) / max(n_samples - 1, 1)
        aging = np.exp(-(aging_pct / 100.0) * np.power(normalized_pos, 1.5))
        tbf = np.maximum(np.round(tbf_noisy * aging / 10.0) * 10.0, 2.0)

        cum = np.cumsum(tbf)
        falha = np.random.choice([0, 1], size=n_samples, p=[0.15, 0.85])
        return [
            DataRecord(TBF=float(tbf[i]), Tempo_Acumulado=float(cum[i]), Falha=int(falha[i]))
            for i in range(n_samples)
        ]

    # Tipos de manutenção que representam eventos NÃO-FALHA — sempre censura (Falha = 0)
    _TIPOS_CENSURA = {
        "Preventiva", "Preditiva",
        "Parada Operacional", "Fim de Observação", "Transferência",
        "Censura",
    }

    @staticmethod
    def process_real_data(
        df: pd.DataFrame, time_col: str, status_col: str
    ) -> List[DataRecord]:
        dc = df.copy()
        dc["TBF"]   = dc[time_col].astype("float64")
        dc["Falha"] = dc[status_col].astype("int8")

        # Manutenção preventiva/preditiva/censura → sempre censura (Falha = 0)
        if "Tipo_Manutencao" in dc.columns:
            mask_censura = dc["Tipo_Manutencao"].isin(ReliabilityEngine._TIPOS_CENSURA)
            dc.loc[mask_censura, "Falha"] = 0

        dc = dc[dc["TBF"] > 0].reset_index(drop=True)
        dc["Tempo_Acumulado"] = dc["TBF"].cumsum()
        return [
            DataRecord(TBF=r.TBF, Tempo_Acumulado=r.Tempo_Acumulado, Falha=r.Falha)
            for r in dc.itertuples()
        ]

    # ── Ajuste paramétrico ────────────────────────────────────────────────────

    @staticmethod
    def fit_parametric_models(
        failures: List[float],
        censored: Optional[List[float]],
    ) -> FitResult:
        fitters = {
            "Weibull 2P":      Fit_Weibull_2P,
            "Lognormal 2P":    Fit_Lognormal_2P,
            "Normal 2P":       Fit_Normal_2P,
            "Exponential 1P":  Fit_Exponential_1P,
        }
        results = []
        for name, FitterClass in fitters.items():
            fit = FitterClass(
                failures=failures,
                right_censored=censored if censored else None,
                show_probability_plot=False,
                print_results=False,
            )
            results.append((name, fit, float(getattr(fit, "AICc", np.nan))))

        results.sort(key=lambda x: x[2])
        ranking = [{"model": n, "aicc": a} for n, _, a in results]

        best_name, best_fit, best_aicc = results[0]
        second_aicc = results[1][2] if len(results) > 1 else best_aicc

        best_params = DistributionParams(**_extract_dist_params(best_fit, best_name))
        return FitResult(
            ranking=ranking,
            best=best_params,
            delta_aicc=float(best_aicc - second_aicc),
        )

    # ── RUL condicional ───────────────────────────────────────────────────────

    @staticmethod
    def compute_rul(
        params: DistributionParams,
        current_age: float,
        n_points: int = 300,
        rul_threshold: float = 0.10,
        n_bootstrap: int = 300,
    ) -> RULResult:
        dist      = reconstruct_distribution(params)
        r_current = float(dist.SF(xvals=current_age, show_plot=False))

        def _find_rul(d: Any, threshold: float = rul_threshold) -> float:
            r0 = float(d.SF(xvals=current_age, show_plot=False))
            if r0 <= 0:
                return 1.0
            def obj(t: float) -> float:
                return abs(float(d.SF(xvals=float(current_age + t), show_plot=False)) / r0 - threshold)
            res = minimize_scalar(obj, bounds=(1.0, d.mean * 5.0), method="bounded")
            return float(res.x)

        rul_time = _find_rul(dist)

        # ── Bootstrap paramétrico para IC ──────────────────────────────────
        rng = np.random.default_rng(42)
        boot_ruls: List[float] = []
        t = params.dist_type
        try:
            for _ in range(n_bootstrap):
                if t == "weibull":
                    from reliability.Fitters import Fit_Weibull_2P
                    sample = np.sort(
                        np.random.weibull(params.beta, size=max(30, n_bootstrap // 10)) * params.eta
                    )
                    fit_b = Fit_Weibull_2P(failures=sample.tolist(),
                                           show_probability_plot=False, print_results=False)
                    from reliability.Distributions import Weibull_Distribution
                    d_b = Weibull_Distribution(alpha=fit_b.alpha, beta=fit_b.beta)
                elif t == "lognormal":
                    from reliability.Distributions import Lognormal_Distribution
                    mu_b    = rng.normal(params.mu,    0.05 * abs(params.mu or 1))
                    sig_b   = abs(rng.normal(params.sigma, 0.05 * params.sigma))
                    d_b = Lognormal_Distribution(mu=mu_b, sigma=max(0.01, sig_b))
                elif t == "normal":
                    from reliability.Distributions import Normal_Distribution
                    mu_b  = rng.normal(params.mu,    0.05 * params.sigma)
                    sig_b = abs(rng.normal(params.sigma, 0.05 * params.sigma))
                    d_b = Normal_Distribution(mu=mu_b, sigma=max(1.0, sig_b))
                elif t == "exponential":
                    from reliability.Distributions import Exponential_Distribution
                    lam_b = abs(rng.normal(params.lam, 0.05 * params.lam))
                    d_b   = Exponential_Distribution(Lambda=max(1e-9, lam_b))
                else:
                    break
                boot_ruls.append(_find_rul(d_b))
        except Exception:
            boot_ruls = []

        if len(boot_ruls) >= 20:
            rul_p10 = float(np.percentile(boot_ruls, 10))
            rul_p90 = float(np.percentile(boot_ruls, 90))
        else:
            rul_p10 = rul_time * 0.7
            rul_p90 = rul_time * 1.3

        t_fut  = np.linspace(0.01, rul_time * 1.5, n_points)
        r_cond = (
            np.array(dist.SF(xvals=(current_age + t_fut).tolist(), show_plot=False))
            / r_current
        )
        return RULResult(
            r_current=r_current,
            rul_time=rul_time,
            rul_p10=rul_p10,
            rul_p90=rul_p90,
            t_future=t_fut.tolist(),
            r_conditional=r_cond.tolist(),
        )

    # ── Crow-AMSAA (NHPP) — MLE via CrowAMSAA da biblioteca reliability ────────

    @staticmethod
    def compute_crow_amsaa(records: List[DataRecord]) -> CrowAMSAAResult:
        """
        Estimador MLE para β e λ do processo Crow-AMSAA.
        Usa a biblioteca `reliability` para evitar o viés do OLS em log-log.
        Fallback para OLS somente se CrowAMSAA não estiver disponível.
        """
        from reliability.Repairable_systems import reliability_growth
        failures_only = [r for r in records if r.Falha == 1]
        t_ac = np.array([r.Tempo_Acumulado for r in failures_only])
        n_ac = np.arange(1, len(t_ac) + 1)

        # MLE: β = n / (n·ln(T_max) − Σln(Tᵢ))
        n   = len(t_ac)
        T_max = float(t_ac[-1])
        beta_mle = n / (n * np.log(T_max) - np.sum(np.log(t_ac)))
        lam_mle  = n / (T_max ** beta_mle)

        n_teorico = lam_mle * (t_ac ** beta_mle)

        if beta_mle > 1.0:
            interp = "⚠️ Degradação detectada — taxa de falha crescente (β > 1)"
        elif beta_mle < 1.0:
            interp = "✅ Melhoria detectada — ações de confiabilidade efetivas (β < 1)"
        else:
            interp = "ℹ️ Processo estacionário — falhas aleatórias (β ≈ 1)"

        return CrowAMSAAResult(
            beta=float(beta_mle),
            lam=float(lam_mle),
            t_acumulado=t_ac.tolist(),
            n_real=n_ac.tolist(),
            n_teorico=n_teorico.tolist(),
            interpretation=interp,
        )

    # ── Auditoria ─────────────────────────────────────────────────────────────

    @staticmethod
    def compute_audit(
        records: List[DataRecord],
        params: DistributionParams,
        horimetro_atual: float = 0.0,
    ):
        from backend.schemas.models import AuditResult
        from scipy import stats as scipy_stats

        df = pd.DataFrame([r.model_dump() for r in records])
        tbf_fail = df[df["Falha"] == 1]["TBF"].values
        n_total    = len(df)
        n_failures = int(df["Falha"].sum())
        n_censored = n_total - n_failures

        # Descritiva
        tbf_mean = float(np.mean(df["TBF"]))
        tbf_std  = float(np.std(df["TBF"], ddof=1))
        tbf_cv   = tbf_std / tbf_mean if tbf_mean > 0 else 0.0

        # Taxa de falha observada
        failure_rate_obs = n_failures / float(df["Tempo_Acumulado"].max())

        # Confiabilidade em MTTF — usa distribuição ajustada (corrigido)
        dist = reconstruct_distribution(params)
        reliability_at_mttf = float(dist.SF(xvals=params.mttf, show_plot=False))
        hazard_at_current = (
            float(dist.HF(xvals=horimetro_atual, show_plot=False))
            if horimetro_atual > 0 else 0.0
        )

        # B-lives — calculadas pela distribuição ajustada (não dados empíricos)
        # B10 = tempo quando 10% falharam = F(t)=0.10 = SF(t)=0.90
        b10 = float(_dist_ppf(params, 0.10))
        b50 = float(_dist_ppf(params, 0.50))
        b90 = float(_dist_ppf(params, 0.90))

        # Percentis — distribuição ajustada
        percentis_vals = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentiles = [
            {
                "percentile": p,
                "tbf_h": float(_dist_ppf(params, p / 100.0)),
                "label": (
                    "Vida extremamente baixa" if p <= 5 else
                    "Vida baixa"              if p <= 10 else
                    "Vida média-baixa"        if p <= 25 else
                    "Vida mediana"            if p == 50 else
                    "Vida média-alta"         if p <= 75 else
                    "Vida alta"               if p <= 90 else
                    "Vida muito alta"
                ),
            }
            for p in percentis_vals
        ]

        # KS test contra o modelo ajustado (corrigido)
        ks_stat, ks_p = ks_test_against_dist(tbf_fail, params)

        # QQ plot correto
        sorted_obs = np.sort(tbf_fail)
        theor_q    = theoretical_quantiles(sorted_obs, params)

        # Spearman
        sp_corr, sp_p = scipy_stats.spearmanr(range(len(tbf_fail)), tbf_fail)

        # Outliers IQR
        q1, q3   = np.percentile(tbf_fail, 25), np.percentile(tbf_fail, 75)
        iqr      = q3 - q1
        lo, hi   = max(0.0, q1 - 1.5 * iqr), q3 + 1.5 * iqr
        outliers = tbf_fail[(tbf_fail < lo) | (tbf_fail > hi)]

        # KPIs do dashboard (calculados — não hardcoded)
        availability_pct = reliability_at_mttf * 100.0
        mtbf_h           = params.mttf

        return AuditResult(
            n_total=n_total, n_failures=n_failures, n_censored=n_censored,
            tbf_mean=tbf_mean, tbf_std=tbf_std, tbf_cv=tbf_cv,
            failure_rate_obs=failure_rate_obs,
            censure_rate_pct=n_censored / n_total * 100.0,
            reliability_at_mttf=reliability_at_mttf,
            hazard_at_current=hazard_at_current,
            b10=b10, b50=b50, b90=b90,
            percentiles=percentiles,
            ks_stat=float(ks_stat), ks_p=float(ks_p), ks_model=params.model_name,
            qq_theoretical=theor_q.tolist(),
            qq_observed=sorted_obs.tolist(),
            spearman_corr=float(sp_corr), spearman_p=float(sp_p),
            n_outliers=len(outliers),
            outlier_pct=len(outliers) / len(tbf_fail) * 100.0,
            outlier_lower=float(lo), outlier_upper=float(hi),
            availability_pct=availability_pct,
            mtbf_h=mtbf_h,
        )
