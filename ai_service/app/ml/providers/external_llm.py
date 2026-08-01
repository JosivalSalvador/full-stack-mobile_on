"""Provider externo: gera texto explicativo via LLM (Ollama Cloud).

Usa o Ollama Cloud (tier gratuito, https://ollama.com) para rodar
modelos abertos hospedados, sem custo por token e sem exigir hardware
próprio. A mesma biblioteca e o mesmo código funcionam apontando para
uma instância local de Ollama, bastando trocar `ollama_host` no .env.

O contrato de entrada é desenhado para nunca receber a senha em si —
apenas metadados já anonimizados (ex: "senha de 8 caracteres, score 1,
padrão de dicionário comum").

Erros de rede, timeout ou de resposta inesperada da API são
capturados e relançados como `LLMProviderError`, para que quem chama
decida como lidar com a falha (ex: seguir sem o resumo em texto, já
que a análise local por si só continua válida).
"""

from dataclasses import dataclass

import httpx
import ollama

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.providers.base import Provider

logger = get_logger(__name__)


class LLMProviderError(Exception):
    """Erro ao chamar o provider de LLM externo."""


@dataclass(frozen=True)
class LLMExplanationRequest:
    """Entrada do provider: apenas metadados anonimizados, nunca a senha."""

    score: int
    warning: str
    suggestions: tuple[str, ...]
    crack_time_display: str


class ExternalLLMProvider(Provider[LLMExplanationRequest, str]):
    """Provider que usa o Ollama Cloud para explicar uma avaliação de
    força de senha em linguagem natural.
    """

    _SYSTEM_PROMPT = (
        "Você explica avaliações de força de senha de forma breve e "
        "clara, em português, para uma pessoa leiga. Nunca peça, "
        "sugira ou mencione a senha em si — você só recebe metadados "
        "já anonimizados. Responda em no máximo 2 frases."
    )

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

    async def run(self, data: LLMExplanationRequest) -> str:
        """Gera uma explicação em texto a partir dos metadados de `data`."""
        prompt = (
            f"Score de força: {data.score}/4. "
            f"Aviso técnico: {data.warning or 'nenhum'}. "
            f"Sugestões técnicas: {'; '.join(data.suggestions) or 'nenhuma'}. "
            f"Tempo estimado de quebra offline: {data.crack_time_display}."
        )

        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
        except (ollama.ResponseError, httpx.HTTPError) as exc:
            logger.error("llm_provider_call_failed", provider=self.name, error=str(exc))
            raise LLMProviderError(f"Falha ao chamar {self.name}: {exc}") from exc

        return response.message.content.strip()
