"""Segurança da própria API: validação de API key e rate limiting.

Este serviço só deveria ser alcançado pelo backend Go, dentro da rede
interna do Docker, nunca exposto diretamente à internet. A checagem
aqui é defesa em profundidade — confirma que quem chama é o backend
de fato, não substitui autenticação do usuário final (isso é
responsabilidade do backend Go, que tem seu próprio módulo de auth).

Rate limit roda em memória, sem Redis: aceitável para um único
processo/réplica. Se o serviço escalar horizontalmente, esta é a
peça a trocar por um limitador com estado compartilhado.
"""

import time
from collections import defaultdict
from collections.abc import Iterable

from app.core.config import get_settings
from app.shared.exceptions import InvalidAPIKeyError, RateLimitExceededError

_request_timestamps: dict[str, list[float]] = defaultdict(list)


def verify_api_key(provided_key: str | None) -> None:
    """Confirma que `provided_key` bate com a API key configurada.

    Levanta `InvalidAPIKeyError` se `provided_key` for None, vazio, ou
    diferente do valor esperado.
    """
    settings = get_settings()
    if not provided_key or provided_key != settings.api_key:
        raise InvalidAPIKeyError


def check_rate_limit(identifier: str) -> None:
    """Confirma que `identifier` não excedeu o limite de requisições na
    janela de tempo configurada.

    `identifier` é tipicamente o IP de origem ou um identificador fixo
    do backend, dependendo de como o middleware que chama esta função
    decide extrair a chamada de origem.

    Levanta `RateLimitExceededError` se o limite já foi atingido.
    """
    settings = get_settings()
    now = time.monotonic()
    window_start = now - settings.rate_limit_window_seconds

    _request_timestamps[identifier] = _prune_old_timestamps(
        _request_timestamps[identifier], window_start
    )

    if len(_request_timestamps[identifier]) >= settings.rate_limit_requests:
        raise RateLimitExceededError

    _request_timestamps[identifier].append(now)


def _prune_old_timestamps(
    timestamps: Iterable[float], window_start: float
) -> list[float]:
    """Descarta timestamps anteriores ao início da janela atual."""
    return [ts for ts in timestamps if ts >= window_start]


def reset_rate_limit_state() -> None:
    """Limpa todo o estado de rate limit em memória.

    Usado exclusivamente por testes, para garantir que um teste não
    vaze contagem de requisição para o próximo.
    """
    _request_timestamps.clear()
