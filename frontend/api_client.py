"""
Cliente HTTP para o backend APM FastAPI.
Camada de abstração entre o Streamlit e a API REST.
Todos os métodos retornam dicts Python prontos para uso no frontend.
"""
from __future__ import annotations

import os
import httpx
from typing import Any, Dict, List, Optional

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8002")
BASE    = f"{BACKEND_URL}/api/v1"
TIMEOUT = 120.0  # segundos — ajuste de modelos RF pode demorar


# ─── Erro tipado — permite mensagens amigáveis no frontend ────────────────────

class BackendError(Exception):
    """Erro retornado pelo backend FastAPI (status 4xx / 5xx)."""
    def __init__(self, endpoint: str, status: int, detail: str) -> None:
        self.endpoint = endpoint
        self.status   = status
        self.detail   = detail
        super().__init__(f"[{status}] {endpoint}: {detail}")


def _raise(r: httpx.Response, path: str) -> None:
    """Converte HTTPStatusError em BackendError com mensagem legível."""
    try:
        detail = r.json().get("detail", r.text)
        if isinstance(detail, list):            # erros de validação Pydantic
            detail = "; ".join(
                f"{'.'.join(str(x) for x in e.get('loc', []))}: {e.get('msg','')}"
                for e in detail
            )
    except Exception:
        detail = r.text or "erro desconhecido"
    raise BackendError(path, r.status_code, str(detail))


# ─── Helpers HTTP ─────────────────────────────────────────────────────────────

def _get(path: str, **params) -> Any:
    r = httpx.get(f"{BASE}{path}", params=params, timeout=TIMEOUT)
    if r.is_error:
        _raise(r, path)
    return r.json()


def _post(path: str, body: Any, **kwargs) -> Any:
    r = httpx.post(f"{BASE}{path}", json=body, timeout=TIMEOUT, **kwargs)
    if r.is_error:
        _raise(r, path)
    return r.json()


def _post_file(path: str, file_bytes: bytes, filename: str, extra_data: dict) -> Any:
    files = {"file": (filename, file_bytes, "text/csv")}
    r = httpx.post(f"{BASE}{path}", files=files, data=extra_data, timeout=TIMEOUT)
    if r.is_error:
        _raise(r, path)
    return r.json()


# ─── Analysis ─────────────────────────────────────────────────────────────────

def simulate(
    n_samples: int,
    equipment_type: str,
    noise_pct: float,
    outlier_pct: float,
    aging_pct: float,
    custom_beta:  Optional[float] = None,
    custom_eta:   Optional[float] = None,
    custom_mu:    Optional[float] = None,
    custom_sigma: Optional[float] = None,
    custom_dist:  Optional[str]   = None,
) -> List[Dict]:
    body: Dict[str, Any] = {
        "n_samples":      n_samples,
        "equipment_type": equipment_type,
        "noise_pct":      noise_pct,
        "outlier_pct":    outlier_pct,
        "aging_pct":      aging_pct,
    }
    if custom_beta  is not None: body["custom_beta"]  = custom_beta
    if custom_eta   is not None: body["custom_eta"]   = custom_eta
    if custom_mu    is not None: body["custom_mu"]    = custom_mu
    if custom_sigma is not None: body["custom_sigma"] = custom_sigma
    if custom_dist  is not None: body["custom_dist"]  = custom_dist
    return _post("/analysis/simulate", body)


def simulate_rich(
    n_samples: int,
    equipment_type: str,
    noise_pct: float,
    outlier_pct: float,
    aging_pct: float,
    tag_ativo: str = "EQP-01A",
    start_date: str = "2021-01-01",
    preco_produto_brl_t: float = 45.0,
    custom_beta:  Optional[float] = None,
    custom_eta:   Optional[float] = None,
    custom_mu:    Optional[float] = None,
    custom_sigma: Optional[float] = None,
    custom_dist:  Optional[str]   = None,
) -> List[Dict]:
    body: Dict[str, Any] = {
        "n_samples":           n_samples,
        "equipment_type":      equipment_type,
        "noise_pct":           noise_pct,
        "outlier_pct":         outlier_pct,
        "aging_pct":           aging_pct,
        "tag_ativo":           tag_ativo,
        "start_date":          start_date,
        "preco_produto_brl_t": preco_produto_brl_t,
    }
    if custom_beta  is not None: body["custom_beta"]  = custom_beta
    if custom_eta   is not None: body["custom_eta"]   = custom_eta
    if custom_mu    is not None: body["custom_mu"]    = custom_mu
    if custom_sigma is not None: body["custom_sigma"] = custom_sigma
    if custom_dist  is not None: body["custom_dist"]  = custom_dist
    return _post("/analysis/simulate-rich", body)


def get_equipment_catalog() -> List[Dict]:
    """Retorna lista de equipamentos do catálogo ISO 14224 com setor, classe e parâmetros Weibull."""
    return _get("/analysis/equipment-catalog")


def validate_iso14224(file_bytes: bytes, filename: str) -> Dict:
    """Valida conformidade ISO 14224 de um CSV e retorna score + lista de issues."""
    files = {"file": (filename, file_bytes, "text/csv")}
    r = httpx.post(f"{BASE}/analysis/validate-iso14224", files=files, timeout=TIMEOUT)
    if r.is_error:
        _raise(r, "/analysis/validate-iso14224")
    return r.json()


def get_csv_columns(file_bytes: bytes, filename: str) -> Dict:
    files = {"file": (filename, file_bytes, "text/csv")}
    r = httpx.post(f"{BASE}/analysis/csv-columns", files=files, timeout=TIMEOUT)
    if r.is_error:
        _raise(r, "/analysis/csv-columns")
    return r.json()


def upload_csv(file_bytes: bytes, filename: str, time_col: str, status_col: str) -> List[Dict]:
    return _post_file(
        "/analysis/upload-csv", file_bytes, filename,
        {"time_col": time_col, "status_col": status_col},
    )


def fit_models(records: List[Dict]) -> Dict:
    return _post("/analysis/fit", records)


def compute_rul(
    dist_params: Dict,
    current_age: float,
    n_points: int = 300,
    rul_threshold: float = 0.10,
    n_bootstrap: int = 300,
) -> Dict:
    return _post("/analysis/rul", {
        "dist_params":    dist_params,
        "current_age":    current_age,
        "n_points":       n_points,
        "rul_threshold":  rul_threshold,
        "n_bootstrap":    n_bootstrap,
    })


def crow_amsaa(records: List[Dict]) -> Dict:
    return _post("/analysis/crow-amsaa", records)


def audit(records: List[Dict], dist_params: Dict, horimetro_atual: float) -> Dict:
    return _post("/analysis/audit", {
        "records":         records,
        "dist_params":     dist_params,
        "horimetro_atual": horimetro_atual,
    })


# ─── ML ───────────────────────────────────────────────────────────────────────

def prescriptive_agent(
    equipment_type: str,
    risk_score: int,
    risk_classification: str,
    rul_hours: float,
    horimetro_atual: float,
    failure_count: int,
    anomaly_count: int,
    trend_type: str,
    degradation_rate: float,
    tag: str,
    weibull_beta:  Optional[float] = None,
    weibull_eta:   Optional[float] = None,
    pmo_tp_otimo:  Optional[float] = None,
    meta:          Optional[Dict]  = None,
) -> Dict:
    """Executa o agente de Manutenção Prescritiva (Claude + Expert System fallback)."""
    return _post("/ml/prescriptive", {
        "equipment_type":      equipment_type,
        "risk_score":          risk_score,
        "risk_classification": risk_classification,
        "rul_hours":           rul_hours,
        "horimetro_atual":     horimetro_atual,
        "failure_count":       failure_count,
        "anomaly_count":       anomaly_count,
        "trend_type":          trend_type,
        "degradation_rate":    degradation_rate,
        "tag":                 tag,
        "weibull_beta":        weibull_beta,
        "weibull_eta":         weibull_eta,
        "pmo_tp_otimo":        pmo_tp_otimo,
        "meta":                meta or {},
    })


def ml_analyze(
    records: List[Dict],
    horimetro_atual: float,
    rul_data: Optional[Dict] = None,
    weibull_params: Optional[Dict] = None,
    risk_thresholds: Optional[Dict] = None,
) -> Dict:
    return _post("/ml/analyze", {
        "records":          records,
        "horimetro_atual":  horimetro_atual,
        "rul_data":         rul_data,
        "weibull_params":   weibull_params,
        "risk_thresholds":  risk_thresholds,
    })


# ─── Maintenance ──────────────────────────────────────────────────────────────

def pmo(beta: float, eta: float, custo_preventivo: float, custo_corretivo: float) -> Dict:
    return _post("/maintenance/pmo", {
        "beta":             beta,
        "eta":              eta,
        "custo_preventivo": custo_preventivo,
        "custo_corretivo":  custo_corretivo,
    })


# ─── Report ───────────────────────────────────────────────────────────────────

def generate_pdf(
    meta: Dict,
    fit: Dict,
    rul: Dict,
    ca: Dict,
    audit: Dict,
    ml: Dict,
    prescriptive: Dict | None = None,
) -> bytes:
    """Solicita ao backend a geração do relatório PDF e retorna os bytes."""
    r = httpx.post(
        f"{BASE}/report/pdf",
        json={
            "meta": meta, "fit": fit, "rul": rul,
            "ca": ca, "audit": audit, "ml": ml,
            "prescriptive": prescriptive or {},
        },
        timeout=60.0,
    )
    if r.is_error:
        _raise(r, "/report/pdf")
    return r.content


# ─── History ──────────────────────────────────────────────────────────────────

def history_save(tag: str, records: List[Dict], meta: Dict) -> Dict:
    """Salva os records da sessão no histórico persistido do ativo."""
    return _post("/history/save", {"tag": tag, "records": records, "meta": meta})


def history_save_rich(tag: str, records: List[Dict], meta: Dict) -> Dict:
    """Salva registros enriquecidos com taxonomia ISO 14224 completa."""
    return _post("/history/save-rich", {"tag": tag, "records": records, "meta": meta})


def history_load_rich(tag: str) -> Optional[List[Dict]]:
    """Carrega histórico ISO 14224 completo do ativo. Retorna None se não existir."""
    try:
        data = _get(f"/history/load-rich/{tag}")
        return data.get("records")
    except BackendError as e:
        if e.status == 404:
            return None
        raise


def history_load(tag: str) -> Optional[List[Dict]]:
    """Carrega histórico acumulado do ativo. Retorna None se não existir."""
    try:
        data = _get(f"/history/load/{tag}")
        return data.get("records")
    except BackendError as e:
        if e.status == 404:
            return None
        raise


def history_assets() -> List[Dict]:
    """Lista ativos com histórico persistido."""
    return _get("/history/assets")


def history_delete(tag: str) -> None:
    """Remove o histórico de um ativo."""
    r = httpx.delete(f"{BASE}/history/{tag}", timeout=TIMEOUT)
    if r.is_error:
        _raise(r, f"/history/{tag}")


# ─── Health ───────────────────────────────────────────────────────────────────

def health_check() -> bool:
    try:
        r = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False
