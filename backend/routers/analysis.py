"""
Router de Análise de Confiabilidade — /api/v1/analysis
Endpoints: simulate, upload-data, fit, rul, crow-amsaa, audit
"""
from __future__ import annotations

import io
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Optional

from backend.schemas.models import (
    SimulationRequest, RichSimulationRequest, RichDataRecord,
    DataRecord, FitResult,
    RULRequest, RULResult, CrowAMSAAResult,
    AuditRequest, AuditResult, DistributionParams,
)
from backend.services.reliability_engine import ReliabilityEngine
from backend.services.rich_simulator import RichSyntheticGenerator

router = APIRouter(prefix="/analysis", tags=["Análise de Confiabilidade"])
engine = ReliabilityEngine()


@router.post("/simulate-rich", response_model=List[RichDataRecord],
             summary="Simula dataset enriquecido ISO 14224 (modo de falha, TTR, datas, financeiro)")
def simulate_rich(req: RichSimulationRequest) -> List[RichDataRecord]:
    """
    Gera dataset completo com 25 colunas por evento:
      - Taxonomia ISO 14224: subcomponente, modo de falha, causa raiz, mecanismo
      - Temporal: data início do intervalo, data do evento, data de retorno à operação
      - TTR (Time To Repair) por LogNormal calibrado por modo de falha
      - Contexto operacional: carga %, temperatura, toneladas processadas
      - Financeiro: custo de reparo BRL, impacto produção (t), lucro cessante BRL
    """
    df = RichSyntheticGenerator.generate(
        n_samples=req.n_samples,
        equipment_type=req.equipment_type,
        noise_pct=req.noise_pct,
        outlier_pct=req.outlier_pct,
        aging_pct=req.aging_pct,
        tag_ativo=req.tag_ativo,
        start_date=req.start_date,
        preco_produto_brl_t=req.preco_produto_brl_t,
        custom_beta=req.custom_beta,
        custom_eta=req.custom_eta,
    )
    return df.to_dict(orient="records")


@router.post("/simulate", response_model=List[DataRecord], summary="Gera dados sintéticos Weibull")
def simulate(req: SimulationRequest) -> List[DataRecord]:
    """
    Simula n_samples registros TBF com perfil Weibull do equipamento selecionado,
    adicionando ruído gaussiano, mortalidade infantil e fadiga sistêmica.
    """
    return engine.generate_synthetic_data(
        req.n_samples, req.equipment_type,
        req.noise_pct, req.outlier_pct, req.aging_pct,
        custom_beta=req.custom_beta,
        custom_eta=req.custom_eta,
    )


@router.post("/upload-csv", response_model=List[DataRecord], summary="Importa CSV real")
async def upload_csv(
    file: UploadFile = File(...),
    time_col:   str  = Form(...),
    status_col: str  = Form(...),
):
    """
    Recebe um CSV com colunas de tempo e status, retorna lista de DataRecord
    normalizada (TBF > 0, Tempo_Acumulado como cumsum).
    """
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    if time_col not in df.columns or status_col not in df.columns:
        raise HTTPException(status_code=422, detail=f"Colunas '{time_col}' ou '{status_col}' não encontradas.")
    if len(df) < 100:
        raise HTTPException(status_code=422, detail=f"Dados insuficientes: {len(df)} registros (mínimo 100).")

    return engine.process_real_data(df, time_col, status_col)


@router.post("/csv-columns", summary="Lista colunas do CSV")
async def csv_columns(file: UploadFile = File(...)) -> dict:
    """Retorna as colunas disponíveis do CSV sem processar os dados."""
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    return {"columns": list(df.columns), "n_rows": len(df)}


@router.post("/fit", response_model=FitResult, summary="Ajuste paramétrico MLE (4 distribuições)")
def fit_models(records: List[DataRecord]) -> FitResult:
    """
    Ajusta Weibull 2P, Lognormal 2P, Normal 2P e Exponencial 1P via MLE.
    Ranqueia por AICc corrigido. Retorna parâmetros do melhor modelo.
    """
    failures = [r.TBF for r in records if r.Falha == 1]
    censored = [r.TBF for r in records if r.Falha == 0]

    if len(failures) < 3:
        raise HTTPException(status_code=422, detail="Mínimo 3 falhas reais para ajuste paramétrico.")

    return engine.fit_parametric_models(failures, censored if censored else None)


@router.post("/rul", response_model=RULResult, summary="Vida Útil Remanescente (RUL condicional + Bootstrap CI)")
def compute_rul(req: RULRequest) -> RULResult:
    """
    Calcula R(t|T) — confiabilidade condicional dado que o ativo sobreviveu até T.
    RUL é o tempo futuro até R_cond = rul_threshold.
    Intervalo de confiança via bootstrap paramétrico (rul_p10 / rul_p90).
    """
    return engine.compute_rul(
        req.dist_params, req.current_age, req.n_points,
        req.rul_threshold, req.n_bootstrap,
    )


@router.post("/crow-amsaa", response_model=CrowAMSAAResult, summary="Análise NHPP Crow-AMSAA (MLE)")
def crow_amsaa(records: List[DataRecord]) -> CrowAMSAAResult:
    """
    Estima β e λ do processo NHPP via MLE (β̂ = n / [n·ln(T) − Σln(Tᵢ)]).
    Corrigido: não usa regressão OLS em log-log (estimador viesado).
    """
    failures_only = [r for r in records if r.Falha == 1]
    if len(failures_only) < 3:
        raise HTTPException(status_code=422, detail="Mínimo 3 falhas para análise Crow-AMSAA.")
    return engine.compute_crow_amsaa(records)


@router.post("/audit", response_model=AuditResult, summary="Auditoria estatística completa")
def audit(req: AuditRequest) -> AuditResult:
    """
    Gera todas as métricas de auditoria:
    - Confiabilidade em MTTF usando distribuição ajustada (não fixo em e^-1)
    - KS test contra o modelo vencedor (não sempre exponencial)
    - QQ plot com quantis teóricos corretos da distribuição ajustada
    - Health score = R(horímetro_atual) via distribuição ajustada
    """
    return engine.compute_audit(req.records, req.dist_params, req.horimetro_atual)
