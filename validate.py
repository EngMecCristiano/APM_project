"""
APM Analytics — Script de Validação Independente
=================================================
Gera dados sintéticos com parâmetros Weibull CONHECIDOS,
chama a API do app e compara os resultados com os valores
teóricos calculados diretamente via scipy.

Uso:
    # Contra o ambiente local (docker compose up)
    python validate.py

    # Contra a produção Railway
    python validate.py --url https://apm-app-production.up.railway.app

Dependências (só stdlib + scipy + numpy + requests):
    pip install scipy numpy requests
"""
from __future__ import annotations

import argparse
import math
import sys
import json

import numpy as np
import requests
from scipy.stats import weibull_min
from scipy.special import gamma as gamma_fn

# ─── Parâmetros verdadeiros (ground truth) ────────────────────────────────────
TRUE_BETA  = 2.5       # forma Weibull
TRUE_ETA   = 1000.0    # escala Weibull (≈ MTTF / Γ(1+1/β))
N_SAMPLES  = 400       # amostras geradas
SEED       = 42
T0         = 600.0     # horímetro atual para cálculo de RUL

TOLERANCE  = 0.05      # 5% de tolerância nos parâmetros ajustados

# ─── Valores teóricos derivados de TRUE_BETA / TRUE_ETA ──────────────────────
def theoretical():
    dist    = weibull_min(c=TRUE_BETA, scale=TRUE_ETA)
    mttf    = TRUE_ETA * gamma_fn(1 + 1 / TRUE_BETA)
    b10     = dist.ppf(0.10)
    b50     = dist.ppf(0.50)
    r_at_t0 = dist.sf(T0)
    # RUL: tempo para R(T0+t)/R(T0) = 0.10  → R(T0+t) = 0.10 * R(T0)
    rul_target = 0.10 * r_at_t0
    # resolve numericamente
    from scipy.optimize import brentq
    try:
        rul_time = brentq(lambda t: dist.sf(T0 + t) - rul_target, 0, 1e6)
    except Exception:
        rul_time = float("nan")
    return {
        "mttf":     mttf,
        "b10":      b10,
        "b50":      b50,
        "r_at_t0":  r_at_t0,
        "rul_time": rul_time,
    }

# ─── Geração de dados sintéticos ─────────────────────────────────────────────
def generate_records(n: int = N_SAMPLES, seed: int = SEED) -> list[dict]:
    rng  = np.random.default_rng(seed)
    dist = weibull_min(c=TRUE_BETA, scale=TRUE_ETA)
    tbfs = dist.rvs(size=n, random_state=seed)
    tbfs = np.clip(tbfs + rng.normal(0, TRUE_ETA * 0.03, n), 10, None)

    records = []
    for i, tbf in enumerate(tbfs):
        records.append({
            "TBF":   round(float(tbf), 2),
            "Falha": 1,
            "N":     i + 1,
        })
    return records

# ─── Chamadas à API ───────────────────────────────────────────────────────────
def call_analysis(base_url: str, records: list[dict], horimetro: float) -> dict:
    payload = {
        "records":          records,
        "horimetro_atual":  horimetro,
        "tag":              "VALIDATE_001",
        "n_bootstrap":      200,
        "threshold":        0.10,
    }
    r = requests.post(f"{base_url}/api/v1/analysis/full", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

# ─── Comparação e relatório ───────────────────────────────────────────────────
def pct_err(estimated, true):
    if true == 0:
        return float("inf")
    return abs(estimated - true) / abs(true) * 100

PASS = "\033[92m✔ PASS\033[0m"
FAIL = "\033[91m✘ FAIL\033[0m"

def check(label: str, estimated, true, tol_pct: float = TOLERANCE * 100) -> bool:
    err = pct_err(estimated, true)
    ok  = err <= tol_pct
    status = PASS if ok else FAIL
    print(f"  {status}  {label:<40}  estimado={estimated:.4f}  teórico={true:.4f}  erro={err:.1f}%")
    return ok

def run_validation(base_url: str):
    print("=" * 65)
    print("  APM Analytics — Validação Independente")
    print(f"  URL: {base_url}")
    print(f"  Ground truth: Weibull β={TRUE_BETA}, η={TRUE_ETA}, N={N_SAMPLES}")
    print("=" * 65)

    # 1. Gerar dados
    print("\n[1] Gerando dados sintéticos…")
    records = generate_records()
    theory  = theoretical()
    print(f"    {len(records)} registros gerados. MTTF teórico = {theory['mttf']:.1f} h")

    # 2. Chamar API
    print("\n[2] Chamando API de análise…")
    try:
        result = call_analysis(base_url, records, T0)
    except requests.exceptions.ConnectionError:
        print(f"\n  ERRO: Não foi possível conectar em {base_url}")
        print("  Verifique se o backend está rodando (docker compose up).")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"\n  ERRO HTTP: {e}")
        print("  Resposta:", e.response.text[:500])
        sys.exit(1)

    fit  = result.get("fit",  {})
    rul  = result.get("rul",  {})
    audit= result.get("audit",{})
    best = fit.get("best", {})

    print(f"    Melhor modelo: {best.get('model_name','?')}  "
          f"AICc={best.get('aicc', float('nan')):.2f}")

    # 3. Validação dos parâmetros Weibull ajustados
    passes = []
    print("\n[3] Parâmetros Weibull ajustados")
    if best.get("dist_type") == "weibull":
        passes.append(check("β (forma)",   best["beta"], TRUE_BETA,  tol_pct=10))
        passes.append(check("η (escala)",  best["eta"],  TRUE_ETA,   tol_pct=10))
    else:
        print(f"  ⚠  Melhor ajuste foi {best.get('model_name')} — β/η não disponíveis")
        print("     (esperado: Weibull — aumentar N_SAMPLES ou ajustar SEED)")

    # 4. Validação das métricas de confiabilidade
    print("\n[4] Métricas de Confiabilidade")
    passes.append(check("MTTF (h)",         audit.get("mtbf_h", 0),           theory["mttf"],     tol_pct=10))
    passes.append(check("B10 Life (h)",     audit.get("b10",    0),           theory["b10"],      tol_pct=10))
    passes.append(check("B50 Life (h)",     audit.get("b50",    0),           theory["b50"],      tol_pct=10))
    passes.append(check(f"R(t={T0:.0f}h)",  rul.get("r_current", 0),          theory["r_at_t0"],  tol_pct=10))

    # 5. Validação do RUL
    print("\n[5] Vida Útil Remanescente (RUL)")
    passes.append(check("RUL (h) @ limiar 10%", rul.get("rul_time", 0), theory["rul_time"], tol_pct=15))

    # 6. Sanidade geral
    print("\n[6] Sanidade Geral")
    km_pts = fit.get("km_points", [])
    passes.append(_check_bool("Curva Kaplan-Meier presente",   len(km_pts) > 0))
    passes.append(_check_bool("Modelos LDA retornados",        len(fit.get("models", [])) >= 3))
    passes.append(_check_bool("Bootstrap IC presente",        bool(rul.get("ci_p10"))))
    passes.append(_check_bool("Crow-AMSAA presente",          "nhpp" in result))
    passes.append(_check_bool("ML retornado",                 "ml"   in result))
    passes.append(_check_bool("Score de risco 0–100",
                              0 <= result.get("ml", {}).get("risk", {}).get("score", -1) <= 100))

    # 7. Resumo
    n_pass = sum(passes)
    n_total= len(passes)
    print("\n" + "=" * 65)
    if n_pass == n_total:
        print(f"\033[92m  RESULTADO: {n_pass}/{n_total} verificações passaram — APP VALIDADO ✔\033[0m")
    else:
        print(f"\033[91m  RESULTADO: {n_pass}/{n_total} passaram — {n_total - n_pass} falha(s) detectada(s)\033[0m")
    print("=" * 65)

    return n_pass == n_total


def _check_bool(label: str, condition: bool) -> bool:
    status = PASS if condition else FAIL
    print(f"  {status}  {label}")
    return condition


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="APM Analytics — Validação Independente")
    parser.add_argument(
        "--url",
        default="http://localhost:8002",
        help="URL base do backend (default: http://localhost:8002)",
    )
    args = parser.parse_args()

    ok = run_validation(args.url.rstrip("/"))
    sys.exit(0 if ok else 1)
