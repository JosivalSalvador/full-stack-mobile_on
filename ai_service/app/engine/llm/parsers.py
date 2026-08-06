"""Interpretação da resposta bruta do Ollama em um objeto tipado.

app/engine/llm/client.py devolve o ollama.ChatResponse cru; este
módulo extrai e valida o texto de explicação, tratando os casos reais
de falha (resposta vazia, resposta cortada por limite de tokens)
antes que o texto chegue a app/modules/vault_audit/pipeline.py.
"""

from dataclasses import dataclass

from ollama import ChatResponse

from app.shared.exceptions import ParsingFailedError

# done_reason "stop" é o único caso em que o Ollama garante que a
# geração terminou naturalmente (o modelo decidiu parar), não por
# limite externo. "length" indica corte por max tokens: o texto pode
# terminar no meio de uma frase.
_ACCEPTED_DONE_REASONS = {"stop"}


@dataclass(frozen=True, slots=True)
class ParsedExplanation:
    """Explicação de força de senha já validada, pronta para persistir.

    prompt_tokens e completion_tokens vêm diretamente dos campos
    prompt_eval_count/eval_count do Ollama (contagem real do
    provider), não da estimativa de app/shared/utils.py
    (estimate_token_count() existe para contextos sem essa contagem
    nativa disponível — aqui ela está, então é usada).
    """

    text: str
    prompt_tokens: int
    completion_tokens: int


def parse_explanation_response(response: ChatResponse) -> ParsedExplanation:
    """Valida e extrai a explicação de um ChatResponse do Ollama.

    Levanta ParsingFailedError se: o conteúdo vier vazio ou só com
    espaços em branco, ou se done_reason indicar que a resposta foi
    cortada antes de terminar naturalmente. Chamado por
    app/engine/llm/client.py logo após receber a resposta da API,
    antes de devolvê-la a quem fez a chamada.
    """
    content = response.message.content

    if content is None or not content.strip():
        raise ParsingFailedError(
            "O Ollama retornou uma resposta vazia para a explicação "
            "de força de senha."
        )

    if response.done_reason is not None:
        if response.done_reason not in _ACCEPTED_DONE_REASONS:
            raise ParsingFailedError(
                "A resposta do Ollama foi interrompida antes de "
                f"terminar (done_reason={response.done_reason!r}); "
                "o texto pode estar incompleto."
            )

    return ParsedExplanation(
        text=content.strip(),
        prompt_tokens=response.prompt_eval_count or 0,
        completion_tokens=response.eval_count or 0,
    )
