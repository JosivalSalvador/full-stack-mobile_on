"""Testes do provider externo de LLM (Ollama Cloud).

Usa `respx` para mockar a chamada HTTP no nível de transporte
(`httpx`, usado pela biblioteca `ollama` por baixo) — nenhum teste
aqui bate na API real, nem consome cota do tier Free.
"""

import httpx
import pytest
import respx

from app.ml.providers.external_llm import (
    ExternalLLMProvider,
    LLMExplanationRequest,
    LLMProviderError,
)

OLLAMA_CHAT_URL = "https://ollama.com/api/chat"


@pytest.fixture
def request_data() -> LLMExplanationRequest:
    return LLMExplanationRequest(
        score=1,
        warning="Esta é uma senha muito comum.",
        suggestions=("Adicione mais palavras.",),
        crack_time_display="menos de um segundo",
    )


class TestExternalLLMProvider:
    @respx.mock
    async def test_run_returns_response_text(
        self, request_data: LLMExplanationRequest
    ) -> None:
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

        provider = ExternalLLMProvider()
        result = await provider.run(request_data)

        assert result == "Essa senha é fraca por ser muito comum."

    @respx.mock
    async def test_api_error_raises_llm_provider_error(
        self, request_data: LLMExplanationRequest
    ) -> None:
        respx.post(OLLAMA_CHAT_URL).mock(
            return_value=httpx.Response(500, json={"error": "internal error"})
        )

        provider = ExternalLLMProvider()

        with pytest.raises(LLMProviderError):
            await provider.run(request_data)

    @respx.mock
    async def test_network_failure_raises_llm_provider_error(
        self, request_data: LLMExplanationRequest
    ) -> None:
        respx.post(OLLAMA_CHAT_URL).mock(side_effect=httpx.ConnectError("timeout"))

        provider = ExternalLLMProvider()

        with pytest.raises(LLMProviderError):
            await provider.run(request_data)

    def test_provider_name(self) -> None:
        assert ExternalLLMProvider().name == "external_ollama"
