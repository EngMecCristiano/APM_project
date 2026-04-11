"""
Serviço de histórico persistido — salva/carrega TBFs por ativo em Parquet.
Armazena em volume Docker: /app/backend/history/<TAG>.parquet
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

HISTORY_DIR = Path("/app/backend/history")
INDEX_FILE  = HISTORY_DIR / "_index.json"


def _ensure_dir() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _safe_tag(tag: str) -> str:
    """Sanitiza o TAG para uso como nome de arquivo."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in tag)


# ─── Salvar ──────────────────────────────────────────────────────────────────

def save(tag: str, records: List[Dict[str, Any]], meta: Dict[str, Any]) -> int:
    """
    Persiste os records (TBF, Tempo_Acumulado, Falha) do ativo.
    Faz merge com histórico existente, eliminando duplicatas por Tempo_Acumulado.
    Retorna o total de registros acumulados.
    """
    _ensure_dir()
    path = HISTORY_DIR / f"{_safe_tag(tag)}.parquet"

    df_new = pd.DataFrame(records)
    df_new["_session"] = datetime.now().isoformat()

    if path.exists():
        df_old = pd.read_parquet(path)
        df_merged = (
            pd.concat([df_old, df_new], ignore_index=True)
            .drop_duplicates(subset=["Tempo_Acumulado"])
            .sort_values("Tempo_Acumulado")
            .reset_index(drop=True)
        )
    else:
        df_merged = df_new.sort_values("Tempo_Acumulado").reset_index(drop=True)

    df_merged.to_parquet(path, index=False)
    _update_index(tag, meta, len(df_merged))
    logger.info("Histórico salvo — TAG=%s  total=%d", tag, len(df_merged))
    return len(df_merged)


# ─── Carregar ─────────────────────────────────────────────────────────────────

def load(tag: str) -> Optional[List[Dict[str, Any]]]:
    """
    Carrega o histórico acumulado do ativo.
    Retorna None se não houver histórico.
    """
    path = HISTORY_DIR / f"{_safe_tag(tag)}.parquet"
    if not path.exists():
        return None

    df = pd.read_parquet(path)
    cols = [c for c in ["TBF", "Tempo_Acumulado", "Falha"] if c in df.columns]
    return df[cols].to_dict(orient="records")


# ─── Listar ativos ────────────────────────────────────────────────────────────

def list_assets() -> List[Dict[str, Any]]:
    """Retorna lista de ativos com histórico e metadata."""
    if not INDEX_FILE.exists():
        return []
    with open(INDEX_FILE) as f:
        return list(json.load(f).values())


# ─── Deletar ──────────────────────────────────────────────────────────────────

def delete(tag: str) -> bool:
    """Remove o histórico de um ativo. Retorna True se existia."""
    path = HISTORY_DIR / f"{_safe_tag(tag)}.parquet"
    if path.exists():
        path.unlink()
        _remove_index(tag)
        return True
    return False


# ─── Índice interno ───────────────────────────────────────────────────────────

def _update_index(tag: str, meta: Dict[str, Any], total: int) -> None:
    index = {}
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            index = json.load(f)
    index[tag] = {
        "tag":               tag,
        "tipo_equipamento":  meta.get("tipo_equipamento", "—"),
        "numero_serie":      meta.get("numero_serie", "—"),
        "total_registros":   total,
        "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _remove_index(tag: str) -> None:
    if not INDEX_FILE.exists():
        return
    with open(INDEX_FILE) as f:
        index = json.load(f)
    index.pop(tag, None)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
