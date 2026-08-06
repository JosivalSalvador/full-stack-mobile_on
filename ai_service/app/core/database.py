"""Engine assíncrono do banco de dados e fábrica de sessões.

Único ponto de criação do engine SQLAlchemy/SQLModel em todo o
serviço. app/api/dependencies.py usa get_db_session() como Depends()
do FastAPI; scripts standalone (scripts/seed_db.py) e workers/
importam session_factory diretamente, já que rodam fora do ciclo de
request/response do FastAPI.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# echo=True em development ajuda a depurar queries geradas pelo
# SQLModel; desligado em produção para não vazar SQL (e dados) nos
# logs estruturados de app/core/logging.py.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    # pool_pre_ping evita erros de "connection already closed" quando
    # o Postgres derruba uma conexão ociosa (comum em containers Docker
    # que reiniciam ou em conexões que passam muito tempo sem uso).
    pool_pre_ping=True,
)

session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # expire_on_commit=False evita que atributos de um objeto ORM
    # fiquem inacessíveis depois de um commit dentro da mesma
    # transação lógica — comportamento padrão do SQLAlchemy que
    # costuma surpreender quem espera reusar o objeto após salvar.
    expire_on_commit=False,
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Fornece uma sessão de banco por requisição, com rollback automático.

    Usado como dependência do FastAPI em app/api/dependencies.py:

        async def get_session():
            async with get_db_session() as session:
                yield session

    Se o bloco `async with` sair por exceção, o rollback acontece
    antes da sessão fechar, evitando que uma transação parcialmente
    escrita vaze para a próxima requisição que reusar a conexão do
    pool.
    """
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Fecha todas as conexões do pool do engine.

    Chamado por app/main.py no shutdown do lifespan, para o serviço
    não deixar conexões TCP penduradas com o Postgres ao encerrar.
    """
    await engine.dispose()
