"""Conexão com o banco de dados.

Este serviço segue "database per service": credencial e schema
próprios, conectados via `database_url` (vem de `core.config`). Nenhum
outro serviço lê ou escreve nas tabelas definidas aqui diretamente.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency do FastAPI: entrega uma sessão de banco por request.

    Uso em uma rota:
        session: AsyncSession = Depends(get_db_session)
    """
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def db_session_context() -> AsyncGenerator[AsyncSession]:
    """Sessão de banco fora do ciclo de uma request HTTP.

    Usada por workers e tarefas em background, que não têm acesso ao
    sistema de Depends do FastAPI.
    """
    async with async_session_factory() as session:
        yield session


async def check_database_connection() -> bool:
    """Confirma que o banco está alcançável. Usado no health check."""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
