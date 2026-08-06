"""Validação de identidade interna (backend Go -> ai_service) e rate
limiting em memória.

O ai_service só vive na rede interna do Docker; o backend Go é a
única porta de entrada da internet. Este módulo não autentica o
usuário final (isso já é responsabilidade do backend Go) — ele
confirma que quem está chamando é o backend de fato, como defesa em
profundidade, e limita a taxa de chamadas por identificador.
"""

import hmac
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.shared.exceptions import InvalidAPIKeyError, RateLimitExceededError

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_internal_api_key(
    api_key: str | None = Depends(_api_key_header),
) -> None:
    """Valida o header X-API-Key contra INTERNAL_API_KEY.

    Usado como dependência do FastAPI em qualquer rota que só deve
    aceitar chamadas do backend Go:

        @router.post("/analyze", dependencies=[Depends(verify_internal_api_key)])

    Em development, se INTERNAL_API_KEY estiver vazia no .env (valor
    ainda não gerado), a validação é pulada — facilita rodar o
    serviço localmente antes da chave real existir. Em production,
    uma INTERNAL_API_KEY vazia é sempre um erro de configuração, não
    uma chamada válida sem chave.
    """
    expected_key = settings.internal_api_key

    if not expected_key:
        if settings.is_production:
            raise InvalidAPIKeyError(
                "INTERNAL_API_KEY não está configurada em produção."
            )
        return

    if api_key is None or not hmac.compare_digest(api_key, expected_key):
        raise InvalidAPIKeyError()


class InMemoryRateLimiter:
    """Rate limiter em memória, por identificador, sem Redis.

    Usa uma janela deslizante simples: para cada identificador, guarda
    os timestamps das chamadas dentro da janela configurada e nega a
    chamada se o total já atingiu o limite. Funciona para um único
    processo do serviço; não compartilha estado entre réplicas — essa
    é a troca explícita feita para não trazer Redis como dependência
    nova (ver .env.example, seção "Rate limiting").
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)

    def check(self, identifier: str) -> None:
        """Registra uma chamada e levanta RateLimitExceededError se o
        identificador excedeu o limite na janela atual.
        """
        now = time.monotonic()
        window_start = now - self._window_seconds

        recent_calls = [t for t in self._calls[identifier] if t > window_start]

        if len(recent_calls) >= self._max_requests:
            self._calls[identifier] = recent_calls
            raise RateLimitExceededError()

        recent_calls.append(now)
        self._calls[identifier] = recent_calls


_rate_limiter = InMemoryRateLimiter(
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


def enforce_rate_limit(request: Request) -> None:
    """Aplica o rate limit em memória, usando o IP do cliente como
    identificador.

    Usado como dependência do FastAPI, tipicamente combinado com
    verify_internal_api_key na mesma rota:

        dependencies=[Depends(verify_internal_api_key), Depends(enforce_rate_limit)]

    Como o único cliente esperado é o backend Go (rede interna), o IP
    de origem já é um identificador estável o bastante — não há
    usuário final autenticado neste nível para usar como chave.
    """
    identifier = request.client.host if request.client else "unknown"
    _rate_limiter.check(identifier)


def get_rate_limiter_dependency() -> Callable[[Request], None]:
    """Permite que testes substituam o rate limiter global via
    app.dependency_overrides, sem precisar esperar a janela de tempo
    real expirar entre casos de teste.
    """
    return enforce_rate_limit
