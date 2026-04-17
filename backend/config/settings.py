"""
APM Analytics — Configurações Centralizadas.
Único ponto de verdade para paths, parâmetros de equipamentos e tunables de ML.
Equipamentos são carregados de equipment_catalog.json — editável sem tocar no código.
"""
from pathlib import Path
import os
import json

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# ─── API ──────────────────────────────────────────────────────────────────────
API_TITLE   = "APM Analytics API"
API_VERSION = "2.0.0"
API_PREFIX  = "/api/v1"

def _cors_origins() -> list[str]:
    env_origins = os.getenv("ALLOWED_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:8501",
        "http://localhost:8502",
        "http://frontend:8501",
        "http://localhost:3000",
        "*",
    ]

CORS_ORIGINS: list[str] = _cors_origins()

# ─── Catálogo de Equipamentos (ISO 14224) ─────────────────────────────────────
_CATALOG_PATH = Path(__file__).parent / "equipment_catalog.json"

def _load_catalog() -> dict:
    try:
        with open(_CATALOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "default_profile": {"beta": 1.5, "eta": 1000.0},
            "default_operational_context": {
                "throughput_t_per_h": 100.0, "temp_base_C": 45.0,
                "temp_std_C": 10.0, "load_mean_pct": 75.0,
                "load_std_pct": 12.0, "cost_per_ttr_h_brl": 5000.0,
                "preco_producao_brl_t": 50.0,
            },
            "default_failure_scenarios": [],
            "environmental_classifications": ["Ambiente Geral"],
            "equipment": [],
        }

EQUIPMENT_CATALOG: dict = _load_catalog()

# Estruturas derivadas — compatibilidade com código existente
EQUIPMENT_PROFILES: dict[str, dict[str, float]] = {
    eq["name"]: eq["weibull"]
    for eq in EQUIPMENT_CATALOG.get("equipment", [])
}
DEFAULT_PROFILE: dict[str, float] = EQUIPMENT_CATALOG.get(
    "default_profile", {"beta": 1.5, "eta": 1000.0}
)
EQUIPMENT_TYPES: list[str] = list(EQUIPMENT_PROFILES.keys())

ENVIRONMENTAL_CLASSIFICATIONS: list[str] = EQUIPMENT_CATALOG.get(
    "environmental_classifications", ["Ambiente Geral"]
)

# ─── Simulação ────────────────────────────────────────────────────────────────
SIM_MIN_SAMPLES = 100
SIM_MAX_SAMPLES = 2000

# ─── ML ───────────────────────────────────────────────────────────────────────
RF_N_ESTIMATORS       = 150
RF_MAX_DEPTH          = 10
RF_RANDOM_STATE       = 42
MIN_SAMPLES_ML        = 10
TRAIN_TEST_SPLIT      = 0.8
ANOMALY_CONTAMINATION = 0.1
FORECAST_STEPS        = 5

# ─── PMO ──────────────────────────────────────────────────────────────────────
PMO_T_RANGE_LOW  = 0.05
PMO_T_RANGE_HIGH = 3.0
PMO_CURVE_POINTS = 250
