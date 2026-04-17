"""
Router de Machine Learning — /api/v1/ml
Endpoints: analyze (pipeline completo ML em uma chamada)
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.schemas.models import MLAnalysisRequest, MLAnalysisResult, PrescriptiveRequest
from backend.services import ml_engine, prescriptive_service
from backend.services.ml_engine import MLOrchestrator

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post("/analyze", response_model=MLAnalysisResult, summary="Pipeline ML completo")
def analyze(req: MLAnalysisRequest) -> MLAnalysisResult:
    """
    Executa em sequência:
    1. Feature Engineering (janelas móveis, lags de falha, cumulativas)
    2. Treinamento Random Forest (80/20 time-split)
    3. Predição do próximo TBF
    4. Forecast multi-passo (5 ciclos à frente)
    5. Análise de tendência (regressão linear, Spearman)
    6. Detecção de anomalias (Isolation Forest)
    7. Score de risco integrado (tendência + anomalias + R(t) + proximidade TBF)
    """
    if len(req.records) < 10:
        raise HTTPException(status_code=422, detail="Mínimo 10 registros para análise ML.")

    return MLOrchestrator.run(
        records=req.records,
        horimetro_atual=req.horimetro_atual,
        rul_data=req.rul_data,
        risk_thresholds=req.risk_thresholds,
    )


@router.post(
    "/prescriptive",
    summary="Agente de Manutenção Prescritiva com IA (ISO 14224)",
)
def prescriptive(req: PrescriptiveRequest) -> Dict[str, Any]:
    """
    Executa o agente Claude (claude-opus-4-7 + tool_use) para gerar plano prescritivo.
    Ferramentas: get_catalog_scenarios · compute_maintenance_window · classify_urgency.
    Fallback automático para Expert System se ANTHROPIC_API_KEY não estiver configurada.
    """
    try:
        from backend.config.settings import EQUIPMENT_CATALOG
        catalog = EQUIPMENT_CATALOG.get("equipment", [])
        return prescriptive_service.run(req.model_dump(), catalog)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Prescriptive endpoint error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
