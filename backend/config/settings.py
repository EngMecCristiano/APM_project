"""
APM Analytics — Configurações Centralizadas.
Único ponto de verdade para paths, parâmetros de equipamentos e tunables de ML.
"""
from pathlib import Path
import os

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# ─── API ──────────────────────────────────────────────────────────────────────
API_TITLE   = "APM Analytics API"
API_VERSION = "2.0.0"
API_PREFIX  = "/api/v1"

def _cors_origins() -> list[str]:
    """Lê ALLOWED_ORIGINS do ambiente (separados por vírgula).
    Em produção, defina ALLOWED_ORIGINS com a URL exata do frontend.
    Em desenvolvimento, permite localhost por padrão.
    """
    env_origins = os.getenv("ALLOWED_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:8501",
        "http://localhost:8502",
        "http://frontend:8501",
        "http://localhost:3000",
        "*",  # fallback desenvolvimento local
    ]

CORS_ORIGINS: list[str] = _cors_origins()

# ─── Perfis de Equipamento (Weibull β, η) ─────────────────────────────────────
EQUIPMENT_PROFILES: dict[str, dict[str, float]] = {
    "Britador Cônico":          {"beta": 2.5, "eta": 1200.0},
    "Peneira Vibratória":       {"beta": 3.0, "eta": 2000.0},
    "Bomba de Polpa":           {"beta": 1.8, "eta":  800.0},
    "Transportador de Correia": {"beta": 1.2, "eta": 3000.0},
}
DEFAULT_PROFILE: dict[str, float] = {"beta": 1.5, "eta": 1000.0}

EQUIPMENT_TYPES: list[str] = list(EQUIPMENT_PROFILES.keys())

# ─── Simulação ────────────────────────────────────────────────────────────────
SIM_MIN_SAMPLES = 100
SIM_MAX_SAMPLES = 1500

# ─── ML ───────────────────────────────────────────────────────────────────────
RF_N_ESTIMATORS       = 150
RF_MAX_DEPTH          = 10
RF_RANDOM_STATE       = 42
MIN_SAMPLES_ML        = 10
TRAIN_TEST_SPLIT      = 0.8
ANOMALY_CONTAMINATION = 0.1
FORECAST_STEPS        = 5

# ─── PMO ──────────────────────────────────────────────────────────────────────
PMO_T_RANGE_LOW  = 0.05   # fração de η (limite inferior)
PMO_T_RANGE_HIGH = 3.0    # fração de η (limite superior)
PMO_CURVE_POINTS = 250
