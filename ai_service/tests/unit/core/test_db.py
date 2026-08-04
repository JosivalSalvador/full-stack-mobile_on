from sqlalchemy.ext.asyncio import AsyncSession

from ai_service.app.core.db import get_db_session


async def test_get_db_session_yields_async_session() -> None:
    session_gen = get_db_session()
    session = await anext(session_gen)

    assert isinstance(session, AsyncSession)

    await session_gen.aclose()
