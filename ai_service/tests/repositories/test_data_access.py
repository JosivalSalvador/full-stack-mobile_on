"""Testes do acesso a dados compartilhado (health check do banco)."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.repositories.data_access import is_database_healthy


class TestIsDatabaseHealthy:
    async def test_returns_true_for_working_session(
        self, test_db_session: AsyncSession
    ) -> None:
        assert await is_database_healthy(test_db_session) is True

    async def test_returns_false_for_unreachable_database(self) -> None:
        # Porta 1 nunca tem Postgres escutando: forma confiável de
        # simular banco inacessível, sem depender de comportamento
        # interno de `session.close()` (que pode reabrir conexão
        # automaticamente, dependendo da implementação do driver).
        unreachable_engine = create_async_engine(
            "postgresql+asyncpg://user:pass@localhost:1/db",
            pool_pre_ping=False,
        )
        session_factory = async_sessionmaker(unreachable_engine)

        async with session_factory() as session:
            assert await is_database_healthy(session) is False

        await unreachable_engine.dispose()
