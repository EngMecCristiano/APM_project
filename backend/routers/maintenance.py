"""
Router de Otimização de Manutenção — /api/v1/maintenance
Endpoints: pmo (Age-Based Replacement Policy)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.models import PMORequest, PMOResult
from backend.services.maintenance_optimizer import MaintenanceOptimizer

router = APIRouter(prefix="/maintenance", tags=["Otimização de Manutenção"])


@router.post("/pmo", response_model=PMOResult, summary="Intervalo ótimo de manutenção preventiva")
def pmo(req: PMORequest) -> PMOResult:
    """
    Minimiza a taxa de custo por hora operada via Teoria da Renovação.
    Requer β > 1 (regime de desgaste). Para β ≤ 1, manutenção corretiva é economicamente superior.

    Modelo: C(tp) = [Cp·R(tp) + Cu·F(tp)] / ∫₀^tp R(x)dx
    """
    if req.beta <= 1.0:
        raise HTTPException(
            status_code=422,
            detail=f"PMO por substituição por idade requer β > 1. β={req.beta:.3f} indica falhas aleatórias.",
        )
    if req.custo_corretivo <= req.custo_preventivo:
        raise HTTPException(
            status_code=422,
            detail="Custo corretivo deve ser maior que preventivo para que a PMO seja economicamente viável.",
        )
    return MaintenanceOptimizer.compute(req)
