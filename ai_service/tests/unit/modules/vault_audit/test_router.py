"""Testes da rota HTTP de auditoria de vault.

Usa `httpx.AsyncClient` com `ASGITransport` para chamar o app FastAPI
de verdade, em memória, sem subir um servidor de rede. As dependências
de banco e providers são substituídas por fakes via
`app.dependency_overrides` — a rota, a validação de schema e o código
de status são testados de forma real; o comportamento de cada peça
interna já é coberto pelos demais arquivos de teste.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.main import app
from app.ml.model_loader import get_external_llm, get_local_model
from tests.unit.conftest import FakeExternalLLM, FakeLocalModel


@pytest_asyncio.fixture
async def client(
    test_db_session: AsyncSession,
    fake_local_model: FakeLocalModel,
    fake_external_llm: FakeExternalLLM,
) -> AsyncGenerator[httpx.AsyncClient]:
    async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_local_model] = lambda: fake_local_model
    app.dependency_overrides[get_external_llm] = lambda: fake_external_llm

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()


class TestVaultAuditRouter:
    async def test_post_returns_200_with_audit_results(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.post(
            "/vault-audit",
            json={
                "user_id": "user-1",
                "items": [{"item_id": "a", "password": "123456"}],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == "user-1"
        assert body["weak_count"] == 1
        assert len(body["items"]) == 1

    async def test_post_password_never_appears_in_response(
        self, client: httpx.AsyncClient
    ) -> None:
        password = "SenhaSuperSecretaDeTeste"

        response = await client.post(
            "/vault-audit",
            json={
                "user_id": "user-1",
                "items": [{"item_id": "a", "password": password}],
            },
        )

        assert password not in response.text

    async def test_post_missing_field_returns_422(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.post("/vault-audit", json={"user_id": "user-1"})

        assert response.status_code == 422

    async def test_post_empty_items_returns_200_with_zero_weak(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.post(
            "/vault-audit", json={"user_id": "user-1", "items": []}
        )

        assert response.status_code == 200
        assert response.json()["weak_count"] == 0
