"""Conexão com o banco de dados.

Este serviço segue "database per service": credencial e schema
próprios, conectados via `database_url` (vem de `core.config`). Nenhum
outro serviço lê ou escreve nas tabelas definidas aqui diretamente.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()


@lru_cache
def get_engine() -> AsyncEngine:
    """Retorna a instância única (cacheada) do engine de conexão.

    Criar dentro de uma função, em vez de na importação do módulo,
    garante que o engine nasce dentro do event loop que já está
    rodando no momento da primeira chamada — não do loop que existia
    quando o módulo foi importado. Mesmo padrão de `get_settings()`
    em `core/config.py`.
    """
    return create_async_engine(
        settings.database_url,
        echo=not settings.is_production,
        pool_pre_ping=True,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retorna a session factory, construída a partir do engine cacheado."""
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency do FastAPI: entrega uma sessão de banco por request.

    Uso em uma rota:
        session: AsyncSession = Depends(get_db_session)
    """
    async with get_session_factory()() as session:
        yield session


@asynccontextmanager
async def db_session_context() -> AsyncGenerator[AsyncSession]:
    """Sessão de banco fora do ciclo de uma request HTTP.

    Usada por workers e tarefas em background, que não têm acesso ao
    sistema de Depends do FastAPI.
    """
    async with get_session_factory()() as session:
        yield session
