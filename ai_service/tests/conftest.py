"""Fixtures compartilhadas por toda a suíte de testes unitários.

Nunca conecta no Postgres de desenvolvimento nem no Ollama real —
providers externos são substituídos por fakes; quando um teste precisa
de banco de verdade, usa `postgres_test` (porta 5433), nunca o de dev.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.ml.providers.base import Provider
from app.ml.providers.external_llm import LLMExplanationRequest
from app.ml.providers.local_model import PasswordStrengthResult

TEST_DATABASE_URL = (
    "postgresql+asyncpg://ai_service_user:ai_service_test_password"
    "@localhost:5433/ai_service_test_db"
)


class FakeLocalModel(Provider[str, PasswordStrengthResult]):
    """Fake do provider local: determinístico, sem rodar zxcvbn de verdade."""

    name = "fake_local"

    async def run(self, data: str) -> PasswordStrengthResult:
        is_weak = data.lower() in {"123456", "password", "senha123"}
        return PasswordStrengthResult(
            score=0 if is_weak else 4,
            warning="Esta é uma senha muito comum." if is_weak else "",
            suggestions=("Adicione mais palavras.",) if is_weak else (),
            crack_time_display="menos de um segundo" if is_weak else "séculos",
            is_weak=is_weak,
        )


class FakeExternalLLM(Provider[LLMExplanationRequest, str]):
    """Fake do provider externo: devolve texto fixo, sem chamar o Ollama."""

    name = "fake_external_llm"

    async def run(self, data: LLMExplanationRequest) -> str:
        return f"Explicação de teste para score {data.score}."


@pytest.fixture
def fake_local_model() -> FakeLocalModel:
    return FakeLocalModel()


@pytest.fixture
def fake_external_llm() -> FakeExternalLLM:
    return FakeExternalLLM()


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
