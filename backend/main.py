"""
APM Analytics — FastAPI Entry Point.
Arquitetura: router-based, stateless, CORS habilitado para o frontend Streamlit.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import (
    API_TITLE, API_VERSION, API_PREFIX, CORS_ORIGINS,
)
from backend.routers import analysis, ml, maintenance, report
from backend.schemas.models import HealthResponse


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[APM] {API_TITLE} v{API_VERSION} — pronto.")
    yield
    print("[APM] Encerrando servidor.")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=(
        "API de Gestão de Performance de Ativos (APM). "
        "Fase 1: Modelagem Estocástica + RUL + Crow-AMSAA. "
        "Fase 2: Machine Learning Prescritivo + PMO."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(analysis.router,     prefix=API_PREFIX)
app.include_router(ml.router,           prefix=API_PREFIX)
app.include_router(maintenance.router,  prefix=API_PREFIX)
app.include_router(report.router,       prefix=API_PREFIX)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION)


@app.get("/", tags=["Health"])
def root() -> dict:
    return {"service": API_TITLE, "version": API_VERSION, "docs": "/docs"}
