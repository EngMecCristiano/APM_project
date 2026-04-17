"""
Router de Análise de Confiabilidade — /api/v1/analysis
Endpoints: simulate, upload-data, fit, rul, crow-amsaa, audit,
           equipment-catalog, validate-iso14224
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
    EquipmentSummary, ISO14224ValidationResult, ISO14224Issue,
)
from backend.services.reliability_engine import ReliabilityEngine
from backend.services.rich_simulator import RichSyntheticGenerator
from backend.config.settings import EQUIPMENT_CATALOG

router = APIRouter(prefix="/analysis", tags=["Análise de Confiabilidade"])
engine = ReliabilityEngine()


# ─── Catálogo de Equipamentos ISO 14224 ───────────────────────────────────────

@router.get("/equipment-catalog", response_model=List[EquipmentSummary],
            summary="Lista equipamentos disponíveis no catálogo ISO 14224")
def get_equipment_catalog() -> List[EquipmentSummary]:
    """Retorna todos os equipamentos do catálogo com seus parâmetros Weibull e setor."""
    result = []
    for eq in EQUIPMENT_CATALOG.get("equipment", []):
        result.append(EquipmentSummary(
            name=eq["name"],
            sector=eq.get("sector", "Geral"),
            iso14224_class=eq.get("iso14224_class", "Machinery"),
            beta=eq["weibull"]["beta"],
            eta=eq["weibull"]["eta"],
            n_scenarios=len(eq.get("failure_scenarios", [])),
        ))
    return result


# ─── Validador de Conformidade ISO 14224 ──────────────────────────────────────

_ISO14224_REQUIRED = {"TBF", "Falha"}
_ISO14224_RECOMMENDED = {
    "Subcomponente", "Modo_Falha", "Causa_Raiz", "Mecanismo_Degradacao",
    "Tipo_Manutencao", "Criticidade", "Boundary", "TTR",
    "Data_Evento", "Data_Retorno_Operacao",
}
_CRITICIDADE_VALID = {"Alta", "Média", "Baixa", "—"}
_BOUNDARY_VALID    = {"Interno", "Externo", "—"}
_TIPO_MANUT_VALID  = {
    "Corretiva", "Corretiva Emergencial",
    "Preventiva", "Preditiva",
    "Parada Operacional", "Fim de Observação", "Transferência",
    "Censura",
}


@router.post("/validate-iso14224", response_model=ISO14224ValidationResult,
             summary="Valida conformidade ISO 14224 de um dataset CSV")
async def validate_iso14224(file: UploadFile = File(...)) -> ISO14224ValidationResult:
    """
    Verifica se o CSV uploaded segue a estrutura ISO 14224:
    - Campos obrigatórios presentes (TBF, Falha)
    - Campos recomendados presentes
    - Valores válidos (Criticidade, Boundary, Tipo_Manutencao)
    - TBF > 0, Falha ∈ {0, 1}, TTR ≥ 0
    Retorna score de conformidade 0–100 e lista de issues.
    """
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao ler CSV: {e}")

    issues: List[ISO14224Issue] = []
    cols = set(df.columns)

    campos_presentes  = sorted(cols & (_ISO14224_REQUIRED | _ISO14224_RECOMMENDED))
    campos_ausentes   = sorted((_ISO14224_REQUIRED | _ISO14224_RECOMMENDED) - cols)

    # 1. Campos obrigatórios
    for campo in _ISO14224_REQUIRED:
        if campo not in cols:
            issues.append(ISO14224Issue(
                campo=campo, severidade="erro",
                descricao=f"Campo obrigatório '{campo}' ausente.",
            ))

    # 2. Campos recomendados
    for campo in _ISO14224_RECOMMENDED:
        if campo not in cols:
            issues.append(ISO14224Issue(
                campo=campo, severidade="aviso",
                descricao=f"Campo recomendado '{campo}' ausente (melhora rastreabilidade).",
            ))

    # 3. Validações de valores
    if "TBF" in cols:
        bad = df.index[df["TBF"].isna() | (df["TBF"] <= 0)].tolist()
        for ln in bad[:10]:
            issues.append(ISO14224Issue(
                campo="TBF", linha=int(ln) + 2, severidade="erro",
                descricao=f"TBF deve ser > 0 (linha {int(ln)+2}: {df.at[ln, 'TBF']}).",
            ))

    if "Falha" in cols:
        bad = df.index[~df["Falha"].isin([0, 1])].tolist()
        for ln in bad[:10]:
            issues.append(ISO14224Issue(
                campo="Falha", linha=int(ln) + 2, severidade="erro",
                descricao=f"Falha deve ser 0 ou 1 (linha {int(ln)+2}: {df.at[ln, 'Falha']}).",
            ))

    if "TTR" in cols:
        bad = df.index[df["TTR"].notna() & (df["TTR"] < 0)].tolist()
        for ln in bad[:5]:
            issues.append(ISO14224Issue(
                campo="TTR", linha=int(ln) + 2, severidade="erro",
                descricao=f"TTR não pode ser negativo (linha {int(ln)+2}).",
            ))

    if "Criticidade" in cols:
        invalidos = df["Criticidade"].dropna()
        invalidos = invalidos[~invalidos.isin(_CRITICIDADE_VALID)]
        if not invalidos.empty:
            issues.append(ISO14224Issue(
                campo="Criticidade", severidade="aviso",
                descricao=f"Valores não padronizados: {invalidos.unique().tolist()[:5]}. "
                           f"Esperado: {sorted(_CRITICIDADE_VALID)}.",
            ))

    if "Boundary" in cols:
        invalidos = df["Boundary"].dropna()
        invalidos = invalidos[~invalidos.isin(_BOUNDARY_VALID)]
        if not invalidos.empty:
            issues.append(ISO14224Issue(
                campo="Boundary", severidade="aviso",
                descricao=f"Valores não padronizados: {invalidos.unique().tolist()[:5]}. "
                           f"Esperado: {sorted(_BOUNDARY_VALID)}.",
            ))

    if "Tipo_Manutencao" in cols:
        invalidos = df["Tipo_Manutencao"].dropna()
        invalidos = invalidos[~invalidos.isin(_TIPO_MANUT_VALID)]
        if not invalidos.empty:
            issues.append(ISO14224Issue(
                campo="Tipo_Manutencao", severidade="aviso",
                descricao=f"Valores não padronizados: {invalidos.unique().tolist()[:5]}.",
            ))

    # Score: penaliza erros (−10 pt) e avisos de campos obrigatórios ausentes (−5 pt)
    n_erros   = sum(1 for i in issues if i.severidade == "erro")
    n_avisos  = sum(1 for i in issues if i.severidade == "aviso")
    score = max(0.0, 100.0 - n_erros * 10.0 - n_avisos * 5.0)

    n_falhas    = int(df["Falha"].sum()) if "Falha" in cols else 0
    n_censurado = len(df) - n_falhas

    conforme = (n_erros == 0)
    resumo = (
        f"Dataset com {len(df)} registros. Score ISO 14224: {score:.0f}/100. "
        f"{n_erros} erro(s), {n_avisos} aviso(s). "
        + ("Conforme." if conforme else "Não conforme — corrija os erros listados.")
    )

    return ISO14224ValidationResult(
        conforme=conforme,
        score_conformidade=score,
        n_registros=len(df),
        n_falhas=n_falhas,
        n_censurados=n_censurado,
        issues=issues,
        campos_presentes=campos_presentes,
        campos_ausentes=campos_ausentes,
        resumo=resumo,
    )


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
        custom_mu=req.custom_mu,
        custom_sigma=req.custom_sigma,
        custom_dist=req.custom_dist,
    )
    return df.to_dict(orient="records")


@router.post("/simulate", response_model=List[DataRecord], summary="Gera dados sintéticos Weibull/Lognormal")
def simulate(req: SimulationRequest) -> List[DataRecord]:
    """
    Simula n_samples registros TBF com perfil Weibull ou Lognormal,
    adicionando ruído gaussiano, mortalidade infantil e fadiga sistêmica.
    """
    return engine.generate_synthetic_data(
        req.n_samples, req.equipment_type,
        req.noise_pct, req.outlier_pct, req.aging_pct,
        custom_beta=req.custom_beta,
        custom_eta=req.custom_eta,
        custom_mu=req.custom_mu,
        custom_sigma=req.custom_sigma,
        custom_dist=req.custom_dist,
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


@router.post("/upload-csv-rich", response_model=List[RichDataRecord],
             summary="Importa CSV ISO 14224 Completo (26 colunas)")
async def upload_csv_rich(file: UploadFile = File(...)) -> List[RichDataRecord]:
    """
    Importa CSV com o esquema completo ISO 14224.
    Colunas obrigatórias: TBF, Falha.
    Aplica regra de censura: qualquer Tipo_Manutencao não-corretivo → Falha = 0.
    """
    _TIPOS_CENSURA = {
        "Preventiva", "Preditiva",
        "Parada Operacional", "Fim de Observação", "Transferência",
        "Censura",
    }
    _STR_DEFAULTS = {
        "OS_Numero": "—", "Tag_Ativo": "EQP-01", "Tipo_Equipamento": "Genérico",
        "Data_Inicio_Intervalo": "", "Data_Evento": "", "Data_Retorno_Operacao": "",
        "Subcomponente": "—", "Modo_Falha": "—", "Causa_Raiz": "—",
        "Mecanismo_Degradacao": "—", "Tipo_Manutencao": "Corretiva",
        "Criticidade": "—", "Boundary": "—",
    }
    _NUM_DEFAULTS = {
        "Num_Evento": 0, "TTR": 0.0, "Horimetro_Inicio": 0.0, "Horimetro_Evento": 0.0,
        "Carga_Media_Pct": 0.0, "Temperatura_Media_C": 0.0, "Toneladas_Processadas": 0.0,
        "Custo_Reparo_BRL": 0.0, "Impacto_Producao_t": 0.0, "Lucro_Cessante_BRL": 0.0,
        "Disponibilidade_Ciclo_Pct": 100.0,
    }

    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    if "TBF" not in df.columns or "Falha" not in df.columns:
        raise HTTPException(status_code=422,
            detail="CSV deve conter ao menos as colunas 'TBF' e 'Falha'.")
    if len(df) < 3:
        raise HTTPException(status_code=422,
            detail=f"Dados insuficientes: {len(df)} registros (mínimo 3).")

    df["TBF"]   = pd.to_numeric(df["TBF"],   errors="coerce")
    df["Falha"] = pd.to_numeric(df["Falha"], errors="coerce").astype("Int64")
    df = df[df["TBF"] > 0].reset_index(drop=True)

    # Regra de censura por Tipo_Manutencao
    if "Tipo_Manutencao" in df.columns:
        mask = df["Tipo_Manutencao"].isin(_TIPOS_CENSURA)
        df.loc[mask, "Falha"] = 0

    df["Tempo_Acumulado"] = df["TBF"].cumsum()

    # Preenche defaults para colunas ausentes
    for col, val in _STR_DEFAULTS.items():
        if col not in df.columns:
            df[col] = val
    for col, val in _NUM_DEFAULTS.items():
        if col not in df.columns:
            df[col] = val

    if "Num_Evento" in df.columns and (df["Num_Evento"] == 0).all():
        df["Num_Evento"] = range(1, len(df) + 1)

    # Garante strings não-nulas
    for col in _STR_DEFAULTS:
        df[col] = df[col].fillna("—").astype(str)

    records = []
    for i, row in df.iterrows():
        falha = int(row["Falha"]) if pd.notna(row["Falha"]) else 0
        records.append(RichDataRecord(
            OS_Numero=str(row["OS_Numero"]),
            Tag_Ativo=str(row["Tag_Ativo"]),
            Tipo_Equipamento=str(row["Tipo_Equipamento"]),
            Num_Evento=int(row["Num_Evento"]),
            Data_Inicio_Intervalo=str(row["Data_Inicio_Intervalo"]),
            Data_Evento=str(row["Data_Evento"]),
            Data_Retorno_Operacao=str(row["Data_Retorno_Operacao"]),
            TBF=float(row["TBF"]),
            TTR=float(row["TTR"]),
            Horimetro_Inicio=float(row["Horimetro_Inicio"]),
            Horimetro_Evento=float(row["Horimetro_Evento"]),
            Falha=falha,
            Subcomponente=str(row["Subcomponente"]),
            Modo_Falha=str(row["Modo_Falha"]),
            Causa_Raiz=str(row["Causa_Raiz"]),
            Mecanismo_Degradacao=str(row["Mecanismo_Degradacao"]),
            Tipo_Manutencao=str(row["Tipo_Manutencao"]),
            Criticidade=str(row["Criticidade"]),
            Boundary=str(row["Boundary"]),
            Carga_Media_Pct=float(row["Carga_Media_Pct"]),
            Temperatura_Media_C=float(row["Temperatura_Media_C"]),
            Toneladas_Processadas=float(row["Toneladas_Processadas"]),
            Custo_Reparo_BRL=float(row["Custo_Reparo_BRL"]),
            Impacto_Producao_t=float(row["Impacto_Producao_t"]),
            Lucro_Cessante_BRL=float(row["Lucro_Cessante_BRL"]),
            Tempo_Acumulado=float(row["Tempo_Acumulado"]),
            Disponibilidade_Ciclo_Pct=float(row["Disponibilidade_Ciclo_Pct"]),
        ))
    return records


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
