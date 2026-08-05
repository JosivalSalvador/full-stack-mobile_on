"""Hierarquia de exceções do ai_service.

Toda exceção de domínio ou infraestrutura levantada pelo serviço herda
de AIServiceError, permitindo que a camada HTTP (app/api/) capture um
único tipo base e traduza para o status code correto sem precisar
conhecer cada exceção específica.
"""


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

    def __init__(self, message: str = "O modelo de ML ainda não está pronto.") -> None:
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


class InvalidAPIKeyError(AIServiceError):
    """A API key enviada em X-API-Key está ausente ou não confere.

    Levantada por app/core/security.py. A chamada só chega aqui vinda
    do backend Go (única porta de entrada da rede interna); esta
    checagem existe como defesa em profundidade, não como
    autenticação de usuário final.
    """

    def __init__(self, message: str = "API key ausente ou inválida.") -> None:
        super().__init__(message, error_code="invalid_api_key")


class RateLimitExceededError(AIServiceError):
    """O identificador de chamada excedeu o limite de requisições na
    janela de tempo configurada.

    Levantada por app/core/security.py, a partir do limitador em
    memória (sem Redis).
    """

    def __init__(self, message: str = "Limite de requisições excedido.") -> None:
        super().__init__(message, error_code="rate_limit_exceeded")
