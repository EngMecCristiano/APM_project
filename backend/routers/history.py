"""
Router de histórico — salva, carrega e gerencia TBFs acumulados por ativo.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import history_service as hs

router = APIRouter(prefix="/history", tags=["History"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SaveRequest(BaseModel):
    tag:     str
    records: List[Dict[str, Any]]
    meta:    Dict[str, Any]


class SaveResponse(BaseModel):
    tag:             str
    total_registros: int
    mensagem:        str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/save", response_model=SaveResponse)
def save_history(req: SaveRequest) -> SaveResponse:
    """Salva os records da sessão atual e faz merge com histórico existente."""
    total = hs.save(req.tag, req.records, req.meta)
    return SaveResponse(
        tag=req.tag,
        total_registros=total,
        mensagem=f"Histórico atualizado — {total} registros acumulados para {req.tag}.",
    )


@router.get("/load/{tag}")
def load_history(tag: str) -> Dict[str, Any]:
    """Carrega o histórico acumulado de um ativo."""
    records = hs.load(tag)
    if records is None:
        raise HTTPException(status_code=404, detail=f"Sem histórico para TAG '{tag}'.")
    return {"tag": tag, "total": len(records), "records": records}


@router.get("/assets")
def list_assets() -> List[Dict[str, Any]]:
    """Lista todos os ativos com histórico persistido."""
    return hs.list_assets()


@router.delete("/{tag}")
def delete_history(tag: str) -> Dict[str, str]:
    """Remove o histórico de um ativo."""
    deleted = hs.delete(tag)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Sem histórico para TAG '{tag}'.")
    return {"mensagem": f"Histórico de '{tag}' removido com sucesso."}
