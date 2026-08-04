"""Teste de integração: fluxo completo de auditoria de vault.

Diferente dos testes unitários, aqui os providers de IA NÃO são
substituídos por fakes no nível do teste — o pipeline roda de verdade
(zxcvbn local de fato, e o provider externo mockado apenas no nível de
transporte HTTP via respx, simulando uma resposta real do Ollama).
O que este teste garante é que a aplicação inteira — rota, service,
pipeline, providers, repository, banco — se encaixa corretamente,
de ponta a ponta, exatamente como rodaria em produção.

Roda contra o Postgres de TESTE (porta 5433), nunca contra o de
desenvolvimento.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest_asyncio
import respx
from sqlalchemy.ext.asyncio import AsyncSession

from ai_service.app.core.db import get_db_session
from app.main import app

OLLAMA_CHAT_URL = "https://ollama.com/api/chat"


@pytest_asyncio.fixture
async def client(
    test_db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient]:
    """Cliente HTTP contra o app real, com apenas o banco trocado pelo
    de teste — os providers de IA (`get_local_model`,
    `get_external_llm`) NÃO são sobrescritos: usam as instâncias reais
    carregadas por `load_providers()` no lifespan da aplicação.
    """

    async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as async_client,
    ):
        yield async_client

    app.dependency_overrides.clear()


class TestVaultAuditFullFlow:
    @respx.mock
    async def test_full_audit_flow_end_to_end(self, client: httpx.AsyncClient) -> None:
        respx.post(OLLAMA_CHAT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "gpt-oss:20b",
                    "message": {
                        "role": "assistant",
                        "content": "Essa senha é fraca por ser muito comum.",
                    },
                    "done": True,
                },
            )
        )

        response = await client.post(
            "/vault-audit",
            json={
                "user_id": "integration-user",
                "items": [
                    {"item_id": "weak-1", "password": "123456"},
                    {"item_id": "strong-1", "password": "x7$kP9#mQ2vL!nR4wZ8"},
                ],
            },
        )

        assert response.status_code == 200
        body = response.json()

        assert body["user_id"] == "integration-user"
        assert body["weak_count"] == 1
        assert len(body["items"]) == 2

        weak_item = next(i for i in body["items"] if i["item_id"] == "weak-1")
        strong_item = next(i for i in body["items"] if i["item_id"] == "strong-1")

        assert weak_item["is_weak"] is True
        assert weak_item["explanation"] is not None
        assert strong_item["is_weak"] is False

        assert "123456" not in response.text

    async def test_health_check_reports_database_status(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["database"] == "ok"

    @respx.mock
    async def test_llm_failure_does_not_break_the_flow(
        self, client: httpx.AsyncClient
    ) -> None:
        respx.post(OLLAMA_CHAT_URL).mock(
            return_value=httpx.Response(500, json={"error": "internal error"})
        )

        response = await client.post(
            "/vault-audit",
            json={
                "user_id": "integration-user-2",
                "items": [{"item_id": "a", "password": "123456"}],
            },
        )

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["is_weak"] is True
        assert item["explanation"] is None
