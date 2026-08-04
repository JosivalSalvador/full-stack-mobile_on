"""Hierarquia de exceções do ai_service.

Toda exceção de domínio ou infraestrutura levantada pelo serviço herda
de AIServiceError, permitindo que a camada HTTP (app/api/) capture um
único tipo base e traduza para o status code correto sem precisar
conhecer cada exceção específica.
"""

from __future__ import annotations


class AIServiceError(Exception):
    """Exceção base de todo o ai_service.

    Carrega uma mensagem legível e um código de erro estável (usado em
    logs e, futuramente, em respostas de API), desacoplando o texto da
    mensagem de qualquer lógica de tratamento.
    """

    def __init__(self, message: str, *, error_code: str) -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ModelNotReadyError(AIServiceError):
    """O ModelRegistry ainda não terminou de carregar o modelo ONNX.

    Levantada quando uma requisição chega antes do `lifespan` de
    app/main.py concluir o carregamento em app/engine/ml/registry.py,
    ou se o carregamento falhou silenciosamente.
    """

    def __init__(
        self, message: str = "O modelo de ML ainda não está pronto."
    ) -> None:
        super().__init__(message, error_code="model_not_ready")


class LLMProviderTimeoutError(AIServiceError):
    """O provider de LLM (Ollama) não respondeu dentro do timeout.

    Levantada por app/engine/llm/client.py após esgotar as tentativas
    de retry com backoff exponencial.
    """

    def __init__(
        self, message: str = "O provedor de LLM não respondeu a tempo."
    ) -> None:
        super().__init__(message, error_code="llm_provider_timeout")


class ParsingFailedError(AIServiceError):
    """A resposta do LLM não validou contra o schema esperado.

    Levantada por app/engine/llm/parsers.py quando, mesmo após as
    estratégias de reparo de JSON, a resposta continua inválida.
    """

    def __init__(
        self, message: str = "Não foi possível interpretar a resposta do LLM."
    ) -> None:
        super().__init__(message, error_code="parsing_failed")


class ItemNotFoundError(AIServiceError):
    """O item do vault referenciado não existe ou não pertence ao usuário.

    Levantada por app/modules/vault_audit/repository.py.
    """

    def __init__(self, message: str = "Item do vault não encontrado.") -> None:
        super().__init__(message, error_code="item_not_found")
