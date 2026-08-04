"""Provedor externo: gera texto explicativo via LLM (Ollama Cloud).

Usa o Ollama Cloud (tier gratuito, https://ollama.com) para rodar
modelos abertos hospedados, sem custo por token e sem exigir hardware
próprio. A mesma biblioteca e o mesmo código funcionam apontando para
uma instância local de Ollama, bastando trocar `ollama_host` no .env.

O texto do prompt em si mora em `domain/vault_audit/prompts.py` — este
módulo só sabe como chamar o Ollama, não o que dizer a ele.
"""

from dataclasses import dataclass

import httpx
import ollama

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.common.llm import LLMProvider, LLMProviderError
from app.domain.vault_audit.prompts import (
    AUDIT_EXPLANATION_SYSTEM_PROMPT,
    build_audit_explanation_prompt,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMExplanationRequest:
    """Entrada do provedor: apenas metadados anonimizados, nunca a senha."""

    score: int
    warning: str
    suggestions: tuple[str, ...]
    crack_time_display: str


class ExternalLLMProvider(LLMProvider[LLMExplanationRequest, str]):
    """Provedor que usa o Ollama Cloud para explicar uma avaliação de
    força de senha em linguagem natural.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.ollama_model
        headers = (
            {"Authorization": f"Bearer {settings.ollama_api_key}"}
            if settings.ollama_api_key
            else {}
        )
        self._client = ollama.AsyncClient(host=settings.ollama_host, headers=headers)

    @property
    def name(self) -> str:
        return "external_ollama"

    async def generate(self, data: LLMExplanationRequest) -> str:
        """Gera uma explicação em texto a partir dos metadados de `data`."""
        prompt = build_audit_explanation_prompt(
            score=data.score,
            warning=data.warning,
            suggestions=data.suggestions,
            crack_time_display=data.crack_time_display,
        )

        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": AUDIT_EXPLANATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
        except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as exc:
            logger.error("llm_provider_call_failed", provider=self.name, error=str(exc))
            raise LLMProviderError(f"Falha ao chamar {self.name}: {exc}") from exc

        return response.message.content.strip()
