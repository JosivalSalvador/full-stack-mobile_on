"""Ponto de entrada do ai_service.

Configura logging, carrega os providers de IA uma única vez (ver
`app/ml/model_loader.py`), monta o app FastAPI com o router agregado
em `api.py`, e expõe um health check que confirma tanto o processo
quanto o banco de dados.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_service.app.api.v1.api import api_router
from ai_service.app.core.db import db_session_context
from app.core.logging import configure_logging, get_logger
from app.ml.model_loader import load_providers
from app.repositories.data_access import is_database_healthy

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Carrega os providers de IA uma única vez, no startup do processo."""
    logger.info("ai_service_starting")
    load_providers()
    logger.info("ai_service_ready")
    yield
    logger.info("ai_service_shutting_down")


app = FastAPI(title="ai_service", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Confirma que o processo está de pé e que o banco está acessível."""
    async with db_session_context() as session:
        database_ok = await is_database_healthy(session)

    return {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unreachable",
    }
