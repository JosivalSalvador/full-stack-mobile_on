"""Cliente HTTP para o provider de LLM externo (Ollama Cloud).

Isola toda a comunicação de rede com o Ollama: monta o AsyncClient uma
única vez, aplica timeout e retry com backoff exponencial, e traduz
falhas da lib ollama para LLMProviderTimeoutError, o único tipo de
erro que app/modules/vault_audit/pipeline.py precisa conhecer desta
camada.

Não implementa circuit breaker: se o Ollama cair, cada chamada ainda
tenta e falha após o retry configurado, sem cortar chamadas futuras
preventivamente. Circuit breaker é uma peça de maior complexidade
(estado entre chamadas, período de meio-aberto) deixada de fora até
uma decisão explícita de adicioná-la.
"""

import asyncio

import ollama
from ollama import ChatResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.engine.llm.parsers import ParsedExplanation, parse_explanation_response
from app.shared.exceptions import LLMProviderTimeoutError

logger = get_logger(__name__)

_REQUEST_TIMEOUT_SECONDS = 15.0
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 0.5

_client = ollama.AsyncClient(
    host=settings.ollama_host,
    headers=(
        {"Authorization": f"Bearer {settings.ollama_api_key}"}
        if settings.ollama_api_key
        else None
    ),
)


async def _call_ollama_once(messages: list[dict[str, str]]) -> ChatResponse:
    """Uma única tentativa de chamada ao Ollama, sem retry.

    stream=False: o serviço precisa da resposta completa antes de
    seguir para o próximo estágio do pipeline (app/engine/pipeline/
    base.py), então streaming não traz benefício aqui.
    """
    return await asyncio.wait_for(
        _client.chat(
            model=settings.ollama_model,
            messages=messages,
            stream=False,
        ),
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )


async def generate_explanation(
    messages: list[dict[str, str]],
) -> ParsedExplanation:
    """Chama o Ollama com retry e devolve a explicação já validada.

    Chamado por app/modules/vault_audit/pipeline.py com as messages
    montadas por app/engine/llm/prompt_manager.py. Faz até
    _MAX_RETRIES tentativas, com espera exponencial entre elas
    (0.5s, 1s, 2s), antes de desistir e levantar
    LLMProviderTimeoutError — que app/modules/vault_audit/pipeline.py
    trata como "explicação indisponível", sem impedir que o resto do
    resultado (score, label do ONNX) seja salvo.
    """
    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = await _call_ollama_once(messages)
            return parse_explanation_response(response)
        except (TimeoutError, ollama.RequestError, ollama.ResponseError) as exc:
            last_error = exc
            logger.warning(
                "ollama_call_failed",
                attempt=attempt + 1,
                max_retries=_MAX_RETRIES,
                error=str(exc),
            )
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))

    raise LLMProviderTimeoutError(
        f"O Ollama falhou após {_MAX_RETRIES} tentativas: {last_error}"
    ) from last_error
