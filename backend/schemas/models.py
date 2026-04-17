"""
Schemas Pydantic — contratos de request/response entre frontend e backend.
Todos os objetos da biblioteca `reliability` são dissolvidos em tipos primitivos
para serialização JSON limpa.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ─── Metadados do ativo ───────────────────────────────────────────────────────

class AssetMeta(BaseModel):
    tag:              str   = "EQP-01A"
    nome:             str   = "Equipamento"
    numero_serie:     str   = "SN-000000"
    tipo_equipamento: str   = "Equipamento Genérico"
    horimetro_atual:  float = 800.0
    data_estudo:      str   = ""
    # Campos ISO 14224 — metadados de identificação e contexto
    fabricante:                 Optional[str] = None
    modelo:                     Optional[str] = None
    data_instalacao:            Optional[str] = None   # YYYY-MM-DD
    classificacao_ambiental:    Optional[str] = None   # ex: "Ambiente Geral", "Offshore — FPSO"
    setor:                      Optional[str] = None   # ex: "Mineração", "Petróleo & Gás"
    responsavel_manutencao:     Optional[str] = None


# ─── Entrada de dados ─────────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    n_samples:      int             = Field(500,  ge=100, le=2000)
    equipment_type: str             = "Britador Cônico"
    noise_pct:      float           = Field(15.0, ge=0.0, le=50.0)
    outlier_pct:    float           = Field(5.0,  ge=0.0, le=20.0)
    aging_pct:      float           = Field(1.5,  ge=0.0, le=5.0)
    # Weibull personalizado
    custom_beta:    Optional[float] = Field(None, gt=0.0, le=10.0)
    custom_eta:     Optional[float] = Field(None, gt=0.0)
    # Lognormal personalizado
    custom_mu:      Optional[float] = Field(None, ge=1.0, le=12.0)
    custom_sigma:   Optional[float] = Field(None, gt=0.0, le=3.0)
    custom_dist:    Optional[str]   = None   # "Weibull" | "Lognormal"


class RichSimulationRequest(SimulationRequest):
    """Simulação enriquecida com taxonomia ISO 14224, datas, TTR e contexto operacional."""
    tag_ativo:           str   = "EQP-01A"
    start_date:          str   = "2021-01-01"   # YYYY-MM-DD
    preco_produto_brl_t: float = Field(45.0, gt=0.0)


class RichDataRecord(BaseModel):
    """Registro completo de evento de manutenção (26 colunas — ISO 14224:2016)."""
    # Identificação
    OS_Numero:            str
    Tag_Ativo:            str
    Tipo_Equipamento:     str
    Num_Evento:           int
    # Temporal
    Data_Inicio_Intervalo:  str
    Data_Evento:            str
    Data_Retorno_Operacao:  str     # vazio para censuras
    # Confiabilidade
    TBF:                  float
    TTR:                  float
    Horimetro_Inicio:     float
    Horimetro_Evento:     float
    Falha:                int
    # Taxonomia ISO 14224
    Subcomponente:          str
    Modo_Falha:             str
    Causa_Raiz:             str
    Mecanismo_Degradacao:   str
    Tipo_Manutencao:        str
    Criticidade:            str
    Boundary:               str     # "Interno" | "Externo" | "—" (ISO 14224 boundary classification)
    # Contexto operacional
    Carga_Media_Pct:        float
    Temperatura_Media_C:    float
    Toneladas_Processadas:  float
    # Financeiro
    Custo_Reparo_BRL:       float
    Impacto_Producao_t:     float
    Lucro_Cessante_BRL:     float
    # Acumulado
    Tempo_Acumulado:              float
    Disponibilidade_Ciclo_Pct:    float


# ─── ISO 14224 — Validação de Conformidade ────────────────────────────────────

class ISO14224Issue(BaseModel):
    campo:      str
    linha:      Optional[int] = None
    severidade: str           # "erro" | "aviso"
    descricao:  str


class ISO14224ValidationResult(BaseModel):
    """Resultado da validação de conformidade ISO 14224 de um dataset."""
    conforme:           bool
    score_conformidade: float      # 0.0 – 100.0
    n_registros:        int
    n_falhas:           int
    n_censurados:       int
    issues:             List[ISO14224Issue]
    campos_presentes:   List[str]
    campos_ausentes:    List[str]
    resumo:             str


# ─── Catálogo de Equipamentos ─────────────────────────────────────────────────

class EquipmentSummary(BaseModel):
    name:           str
    sector:         str
    iso14224_class: str
    beta:           float
    eta:            float
    n_scenarios:    int


class DataRecord(BaseModel):
    """Registro TBF serializado (uma linha do DataFrame)."""
    TBF:              float
    Tempo_Acumulado:  float
    Falha:            int


# ─── Parâmetros da distribuição ajustada ──────────────────────────────────────

class DistributionParams(BaseModel):
    """
    Representa os parâmetros do modelo de sobrevivência vencedor.
    Campos opcionais dependem do tipo de distribuição:
      weibull     → beta, eta
      lognormal   → mu, sigma
      normal      → mu, sigma
      exponential → lam
    """
    model_name: str
    dist_type:  str           # 'weibull' | 'lognormal' | 'normal' | 'exponential'
    beta:       Optional[float] = None
    eta:        Optional[float] = None
    mu:         Optional[float] = None
    sigma:      Optional[float] = None
    lam:        Optional[float] = None
    mttf:       float = 0.0
    variance:   float = 0.0
    aicc:       float = 0.0


# ─── Resultados de análise paramétrica ───────────────────────────────────────

class FitResult(BaseModel):
    ranking:    List[Dict[str, Any]]  # [{"model": str, "aicc": float}, ...]
    best:       DistributionParams
    delta_aicc: float


# ─── RUL ──────────────────────────────────────────────────────────────────────

class RULRequest(BaseModel):
    dist_params:   DistributionParams
    current_age:   float
    n_points:      int   = 300
    rul_threshold: float = Field(0.10, gt=0.0, lt=1.0,
                                 description="Limiar de R_cond para o RUL (padrão 10%)")
    n_bootstrap:   int   = Field(300, ge=50, le=2000,
                                 description="Amostras para intervalo de confiança Bootstrap")


class RULResult(BaseModel):
    r_current:     float
    rul_time:      float          # estimativa pontual
    rul_p10:       float = 0.0   # IC Bootstrap — percentil 10 (otimista)
    rul_p90:       float = 0.0   # IC Bootstrap — percentil 90 (pessimista)
    t_future:      List[float]
    r_conditional: List[float]


# ─── Crow-AMSAA ───────────────────────────────────────────────────────────────

class CrowAMSAAResult(BaseModel):
    beta:           float
    lam:            float
    t_acumulado:    List[float]
    n_real:         List[int]
    n_teorico:      List[float]
    interpretation: str


# ─── Auditoria ────────────────────────────────────────────────────────────────

class AuditRequest(BaseModel):
    records:    List[DataRecord]
    dist_params: DistributionParams
    horimetro_atual: float = 0.0


class AuditResult(BaseModel):
    # Contagens
    n_total:              int
    n_failures:           int
    n_censored:           int
    # Descritiva
    tbf_mean:             float
    tbf_std:              float
    tbf_cv:               float
    # Métricas de confiabilidade (corrigidas — usam distribuição ajustada)
    failure_rate_obs:     float   # falhas / tempo_total
    censure_rate_pct:     float
    reliability_at_mttf:  float   # dist.SF(mttf) — válido p/ qualquer distribuição
    hazard_at_current:    float   # taxa de falha instantânea h(t_atual)
    # B-lives
    b10:                  float
    b50:                  float
    b90:                  float
    # Percentis completos
    percentiles:          List[Dict[str, Any]]
    # KS test contra o melhor modelo (não sempre exponencial)
    ks_stat:              float
    ks_p:                 float
    ks_model:             str
    # QQ plot correto (quantis teóricos da distribuição ajustada)
    qq_theoretical:       List[float]
    qq_observed:          List[float]
    # Tendência Spearman
    spearman_corr:        float
    spearman_p:           float
    # Outliers (IQR)
    n_outliers:           int
    outlier_pct:          float
    outlier_lower:        float
    outlier_upper:        float
    # Dashboard KPIs calculados
    availability_pct:     float   # R(mttf) * 100 — fração do tempo operacional teórico
    mtbf_h:               float


# ─── ML ───────────────────────────────────────────────────────────────────────

class MLAnalysisRequest(BaseModel):
    records:          List[DataRecord]
    horimetro_atual:  float
    rul_data:         Optional[Dict[str, Any]] = None
    weibull_params:   Optional[Dict[str, Any]] = None
    risk_thresholds:  Optional[Dict[str, int]] = None  # {"critical": 70, "alto": 50, "medio": 30}


class TrendResult(BaseModel):
    slope:           float
    intercept:       float
    r_squared:       float
    p_value:         float
    trend_type:      str
    color:           str
    degradation_rate: float


class AnomalyResult(BaseModel):
    indices:      List[int]
    values:       List[float]
    scores:       List[float]
    anomaly_mask: List[bool]
    count:        int


class MLMetrics(BaseModel):
    r2:      float
    mae:     float
    rmse:    float
    samples: int
    y_test:  List[float]
    y_pred:  List[float]


class ForecastResult(BaseModel):
    next_tbf:    Optional[float]
    future_tbfs: List[float]


class FeatureImportance(BaseModel):
    features:    List[str]
    importances: List[float]


class RiskComponents(BaseModel):
    tendency_tbf:   int
    anomalies_if:   int
    reliability_rt: int
    proximity_ml:   int


class RiskResult(BaseModel):
    score:          int
    classification: str
    urgency:        str
    color:          str
    action:         str
    components:     RiskComponents


class MLAnalysisResult(BaseModel):
    trend:              TrendResult
    anomalies:          AnomalyResult
    metrics:            MLMetrics
    forecast:           ForecastResult
    feature_importance: Optional[FeatureImportance]
    risk:               RiskResult


# ─── PMO ──────────────────────────────────────────────────────────────────────

class PMORequest(BaseModel):
    beta:             float = Field(..., gt=1.0, description="β > 1 (regime de desgaste)")
    eta:              float = Field(..., gt=0.0)
    custo_preventivo: float = Field(1.0, gt=0.0)
    custo_corretivo:  float = Field(5.0, gt=0.0)


class PMOResult(BaseModel):
    tp_otimo:            float
    disponibilidade:     float
    reducao_custo_pct:   float
    custo_na_otimo:      float
    custo_corretivo_puro: float
    t_range:             List[float]
    custo_curva:         List[float]


# ─── Manutenção Prescritiva ───────────────────────────────────────────────────

class PrescriptiveRequest(BaseModel):
    """Dados do ativo para o agente de Manutenção Prescritiva."""
    equipment_type:      str
    risk_score:          int
    risk_classification: str
    rul_hours:           float
    horimetro_atual:     float
    failure_count:       int
    anomaly_count:       int
    trend_type:          str
    degradation_rate:    float
    tag:                 str
    weibull_beta:        Optional[float] = None
    weibull_eta:         Optional[float] = None
    pmo_tp_otimo:        Optional[float] = None
    meta:                Dict[str, Any]  = Field(default_factory=dict)


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:  str = "ok"
    version: str
