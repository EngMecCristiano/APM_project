"""
Serviço de Machine Learning — Fase 2.
Feature Engineering, predição TBF (Random Forest), detecção de anomalias
(Isolation Forest) e análise de tendência (regressão linear).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple

from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from scipy import stats

from backend.config.settings import (
    RF_N_ESTIMATORS, RF_MAX_DEPTH, RF_RANDOM_STATE,
    MIN_SAMPLES_ML, TRAIN_TEST_SPLIT,
    ANOMALY_CONTAMINATION, FORECAST_STEPS,
)
from backend.schemas.models import (
    DataRecord, TrendResult, AnomalyResult, MLMetrics,
    ForecastResult, FeatureImportance,
)


# ─── Feature Engineering ──────────────────────────────────────────────────────

class FeatureEngineer:
    """Extrai features de memória de fadiga estrutural a partir de séries TBF."""

    WINDOWS = (3, 5, 10)

    @staticmethod
    def extract(df: pd.DataFrame) -> pd.DataFrame:
        """
        Features de janela móvel (MA, Std, Slope) + acumuladas + falha + modo de falha.
        Captura degradação de curto prazo, volatilidade, memória histórica e padrão por modo.
        """
        out = df.copy().sort_values("Tempo_Acumulado").reset_index(drop=True)

        for w in FeatureEngineer.WINDOWS:
            if len(out) >= w:
                out[f"TBF_MA_{w}"]  = out["TBF"].rolling(w, min_periods=1).mean()
                out[f"TBF_Std_{w}"] = out["TBF"].rolling(w, min_periods=1).std()
                out[f"TBF_Slope_{w}"] = out["TBF"].rolling(w).apply(
                    lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0.0,
                    raw=True,
                )

        if "Falha" in out.columns:
            out["Falha_Lag_1"]  = out["Falha"].shift(1)
            out["Falha_Lag_2"]  = out["Falha"].shift(2)
            out["Failure_Rate"] = out["Falha"].rolling(5, min_periods=1).mean() * 100

        out["TBF_Cummean"] = out["TBF"].expanding().mean()
        out["TBF_Cumstd"]  = out["TBF"].expanding().std()

        # ── Features de Causa_Parada (só quando coluna presente e variada) ──────
        if "Causa_Parada" in out.columns:
            modos = out["Causa_Parada"].fillna("—")
            # Label encoding: rank por frequência (modo mais comum = 0)
            freq_rank = {m: i for i, m in enumerate(modos.value_counts().index)}
            out["Causa_Code"] = modos.map(freq_rank).fillna(0).astype(float)
            # Lag-1: causa da parada do evento anterior (sem data leakage)
            out["Causa_Code_Lag1"] = out["Causa_Code"].shift(1).fillna(0)
            # Risk encoding: média de TBF por modo usando apenas falhas reais
            fail_mask = out["Falha"] == 1 if "Falha" in out.columns else pd.Series(True, index=out.index)
            global_mean = out.loc[fail_mask, "TBF"].mean() if fail_mask.any() else out["TBF"].mean()
            causa_tbf = out.loc[fail_mask].groupby("Causa_Parada")["TBF"].mean()
            out["Causa_TBF_Risk"] = modos.map(causa_tbf).fillna(global_mean)

        return out.fillna(0)


# ─── Predição TBF ─────────────────────────────────────────────────────────────

class TBFPredictor:
    """Random Forest para predição e forecast multi-passo do TBF."""

    def __init__(self) -> None:
        self._fe     = FeatureEngineer()
        self._model: Optional[RandomForestRegressor] = None
        self._scaler = StandardScaler()
        self._feature_cols: List[str] = []
        self.is_trained = False

    def _get_feature_cols(self, df_feat: pd.DataFrame) -> List[str]:
        return [
            c for c in df_feat.columns
            if c.startswith(("TBF_MA", "TBF_Std", "TBF_Slope", "Falha_", "TBF_Cum",
                             "Causa_Code", "Causa_TBF"))
        ]

    def train(self, df: pd.DataFrame) -> MLMetrics:
        df_feat = self._fe.extract(df)
        self._feature_cols = self._get_feature_cols(df_feat)

        X = np.array([df_feat[self._feature_cols].iloc[i].values for i in range(len(df_feat) - 1)])
        y = np.array([df_feat["TBF"].iloc[i + 1] for i in range(len(df_feat) - 1)])

        if len(X) < MIN_SAMPLES_ML:
            return MLMetrics(r2=0.0, mae=0.0, rmse=0.0, samples=len(X),
                             y_test=[], y_pred=[])

        split = int(len(X) * TRAIN_TEST_SPLIT)
        X_tr, X_te = X[:split], X[split:]
        y_tr, y_te = y[:split], y[split:]

        X_tr_s = self._scaler.fit_transform(X_tr)
        X_te_s = self._scaler.transform(X_te)

        self._model = RandomForestRegressor(
            n_estimators=RF_N_ESTIMATORS,
            max_depth=RF_MAX_DEPTH,
            random_state=RF_RANDOM_STATE,
        )
        self._model.fit(X_tr_s, y_tr)
        y_pred = self._model.predict(X_te_s)
        self.is_trained = True

        return MLMetrics(
            r2=float(r2_score(y_te, y_pred)),
            mae=float(mean_absolute_error(y_te, y_pred)),
            rmse=float(np.sqrt(mean_squared_error(y_te, y_pred))),
            samples=len(X),
            y_test=y_te.tolist(),
            y_pred=y_pred.tolist(),
        )

    def predict_next(self, df: pd.DataFrame) -> Optional[float]:
        if not self.is_trained or self._model is None:
            return None
        df_feat = self._fe.extract(df)
        cols = [c for c in self._feature_cols if c in df_feat.columns]
        last = df_feat[cols].iloc[-1].values.reshape(1, -1)
        return float(self._model.predict(self._scaler.transform(last))[0])

    def forecast_multiple(self, df: pd.DataFrame, n_steps: int = FORECAST_STEPS) -> List[float]:
        """Forecast iterativo: cada previsão alimenta o passo seguinte."""
        forecasts: List[float] = []
        df_temp = df.copy()
        for _ in range(n_steps):
            nxt = self.predict_next(df_temp)
            if nxt is None:
                break
            forecasts.append(nxt)
            new_row = pd.DataFrame({
                "TBF":             [nxt],
                "Tempo_Acumulado": [df_temp["Tempo_Acumulado"].iloc[-1] + nxt],
                "Falha":           [1],
            })
            df_temp = pd.concat([df_temp, new_row], ignore_index=True)
        return forecasts

    def feature_importance(self) -> Optional[FeatureImportance]:
        if self._model is None or not self._feature_cols:
            return None
        imp = self._model.feature_importances_
        order = np.argsort(imp)
        return FeatureImportance(
            features=[self._feature_cols[i] for i in order],
            importances=[float(imp[i]) for i in order],
        )


# ─── Análise de Tendência ─────────────────────────────────────────────────────

class TrendAnalyzer:
    """
    Regressão linear sobre índice de ciclo × TBF.
    slope < 0 → degradação (falhas mais frequentes)
    slope > 0 → melhoria (manutenções efetivas)
    """

    @staticmethod
    def analyze(tbf_series: np.ndarray) -> TrendResult:
        x = np.arange(len(tbf_series))
        slope, intercept, r_value, p_value, _ = stats.linregress(x, tbf_series)
        mean_tbf = float(np.mean(tbf_series))

        if slope < -0.5 and p_value < 0.05:
            trend_type, color = "Degradação Acelerada", "red"
        elif slope < -0.1:
            trend_type, color = "Degradação Moderada", "orange"
        elif slope > 0.5 and p_value < 0.05:
            trend_type, color = "Melhoria Contínua", "green"
        else:
            trend_type, color = "Estável", "gray"

        return TrendResult(
            slope=float(slope),
            intercept=float(intercept),
            r_squared=float(r_value ** 2),
            p_value=float(p_value),
            trend_type=trend_type,
            color=color,
            degradation_rate=(slope / mean_tbf * 100) if mean_tbf > 0 else 0.0,
        )


# ─── Detecção de Anomalias ────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Isolation Forest sobre vetores (TBF_t, TBF_{t-1}, TBF_{t-2}).
    Anomalias em mineração: mortalidade infantil, choques mecânicos, censura mascarada.
    """

    @staticmethod
    def detect(
        tbf_series: np.ndarray,
        contamination: float = ANOMALY_CONTAMINATION,
    ) -> AnomalyResult:
        n = len(tbf_series)
        if n < MIN_SAMPLES_ML:
            return AnomalyResult(
                indices=[], values=[], scores=list(np.zeros(n)),
                anomaly_mask=[False] * n, count=0,
            )

        X = np.column_stack([tbf_series, np.roll(tbf_series, 1), np.roll(tbf_series, 2)])[2:]
        X_scaled = StandardScaler().fit_transform(X)

        clf = IsolationForest(contamination=contamination, random_state=RF_RANDOM_STATE)
        pred   = clf.fit_predict(X_scaled)
        scores = clf.score_samples(X_scaled)

        mask       = np.zeros(n, dtype=bool)
        full_scores = np.zeros(n)
        mask[2:]       = (pred == -1)
        full_scores[2:] = scores

        anom_idx = np.where(mask)[0]
        return AnomalyResult(
            indices=anom_idx.tolist(),
            values=[float(tbf_series[i]) for i in anom_idx],
            scores=full_scores.tolist(),
            anomaly_mask=mask.tolist(),
            count=int(np.sum(mask)),
        )


# ─── Orquestrador completo ────────────────────────────────────────────────────

class MLOrchestrator:
    """Executa todo o pipeline ML em uma chamada e retorna resultado consolidado."""

    @staticmethod
    def run(
        records: List[DataRecord],
        horimetro_atual: float,
        rul_data: Optional[Dict[str, Any]] = None,
        risk_thresholds: Optional[Dict[str, int]] = None,
    ):
        from backend.schemas.models import MLAnalysisResult, RiskResult, RiskComponents

        df = pd.DataFrame([r.model_dump() for r in records])
        tbf = df["TBF"].values

        # Treina predictor
        predictor = TBFPredictor()
        metrics   = predictor.train(df)
        next_tbf  = predictor.predict_next(df)
        future    = predictor.forecast_multiple(df) if next_tbf else []
        feat_imp  = predictor.feature_importance()

        # Análises independentes
        trend    = TrendAnalyzer.analyze(tbf)
        anomalies = AnomalyDetector.detect(tbf)

        # Risk score integrado
        risk = _compute_risk(trend, anomalies.count, len(records),
                             next_tbf, horimetro_atual, rul_data,
                             risk_thresholds=risk_thresholds)

        return MLAnalysisResult(
            trend=trend,
            anomalies=anomalies,
            metrics=metrics,
            forecast=ForecastResult(next_tbf=next_tbf, future_tbfs=future),
            feature_importance=feat_imp,
            risk=risk,
        )


# ─── Risk Score ───────────────────────────────────────────────────────────────

def _compute_risk(
    trend: TrendResult,
    anomaly_count: int,
    total_samples: int,
    next_tbf: Optional[float],
    horimetro_atual: float,
    rul_data: Optional[Dict[str, Any]],
    risk_thresholds: Optional[Dict[str, int]] = None,
):
    from backend.schemas.models import RiskResult, RiskComponents

    # C1: Tendência (0-30)
    if trend.slope < -0.5 and trend.p_value < 0.05:
        c1 = 30
    elif trend.slope < -0.1:
        c1 = 20
    elif trend.slope > 0.5 and trend.p_value < 0.05:
        c1 = 5
    else:
        c1 = 10

    # C2: Anomalias Isolation Forest (0-25)
    c2 = min(25, int((anomaly_count / max(total_samples, 1)) * 150))

    # C3: Confiabilidade R(t) atual (0-30)
    c3 = 0
    if rul_data:
        r_current = float(rul_data.get("r_current", 1.0))
        if   r_current < 0.2: c3 = 30
        elif r_current < 0.4: c3 = 22
        elif r_current < 0.6: c3 = 15
        elif r_current < 0.8: c3 = 8
        else:                  c3 = 3

    # C4: Proximidade ao próximo TBF (0-15)
    c4 = 0
    if next_tbf and next_tbf > 0 and horimetro_atual > 0:
        ratio = horimetro_atual / next_tbf
        if   ratio >= 0.9: c4 = 15
        elif ratio >= 0.7: c4 = 10
        elif ratio >= 0.5: c4 = 5
        else:              c4 = 2

    score = c1 + c2 + c3 + c4

    thr_critical = (risk_thresholds or {}).get("critical", 70)
    thr_alto     = (risk_thresholds or {}).get("alto",     50)
    thr_medio    = (risk_thresholds or {}).get("medio",    30)

    if score >= thr_critical:
        cls, urgency, color = "CRÍTICO", "Intervenção imediata necessária", "#DC2626"
        action = "Parar ativo para inspeção e manutenção corretiva."
    elif score >= thr_alto:
        cls, urgency, color = "ALTO", "Planejar manutenção urgente (< 72h)", "#EA580C"
        action = "Escalonar ordem de manutenção preventiva com alta prioridade."
    elif score >= thr_medio:
        cls, urgency, color = "MÉDIO", "Monitoramento intensificado", "#CA8A04"
        action = "Aumentar frequência de inspeção. Planejar intervenção no próximo ciclo."
    else:
        cls, urgency, color = "BAIXO", "Operação dentro dos parâmetros", "#059669"
        action = "Manter plano de manutenção preventiva vigente."

    return RiskResult(
        score=score, classification=cls, urgency=urgency,
        color=color, action=action,
        components=RiskComponents(
            tendency_tbf=c1, anomalies_if=c2, reliability_rt=c3, proximity_ml=c4,
        ),
    )
