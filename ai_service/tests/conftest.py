"""Fixtures compartilhadas entre `tests/unit/` e `tests/integration/`.

Fica aqui, no topo de `tests/`, porque é visível para ambas as
subpastas — um conftest.py só alcança quem está abaixo dele na árvore.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

TEST_DATABASE_URL = (
    "postgresql+asyncpg://ai_service_user:ai_service_test_password"
    "@localhost:5433/ai_service_test_db"
)


@pytest_asyncio.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession]:
    """Sessão contra o Postgres de TESTE, com schema criado e limpo a
    cada teste que usar esta fixture.
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()
