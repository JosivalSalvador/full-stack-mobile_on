"""Configuração de logging estruturado do ai_service, via structlog.

Todo log do serviço passa por aqui: em vez de `print()` ou
`logging.getLogger(__name__)` espalhado pelos módulos, cada arquivo
chama `get_logger(__name__)` deste módulo e recebe um logger já
configurado para emitir JSON estruturado — formato que
app/api/middleware.py aproveita para anexar o X-Correlation-ID a cada
linha de log de uma requisição.
"""

import logging
import sys
from typing import cast

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Configura o structlog e o logging padrão da stdlib juntos.

    Precisa ser chamada uma única vez, no startup do serviço (por
    app/main.py, no lifespan) ou no início de scripts standalone
    (scripts/train.py, workers/app.py), antes de qualquer chamada a
    get_logger(). Sem essa chamada, o structlog cai no comportamento
    padrão dele, sem o formato JSON nem o nível configurado.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level.upper(),
    )

    structlog.configure(
        processors=[
            # Adiciona nível, timestamp e nome do logger a cada evento
            # antes de qualquer processador específico de formato.
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # JSON em produção (fácil de indexar em log aggregator);
            # saída legível por humano em desenvolvimento local.
            structlog.processors.JSONRenderer()
            if settings.is_production
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level.upper()]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Retorna um logger nomeado, já configurado pelo structlog.

    Uso padrão em qualquer módulo do serviço:

        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("evento_ocorreu", chave=valor)

    O nome (`__name__`) aparece no log para rastrear a origem de cada
    linha, e os pares chave=valor viram campos estruturados em vez de
    texto solto interpolado na mensagem.

    structlog.get_logger() retorna Any no ponto de vista do mypy (a
    tipagem do structlog não amarra o retorno ao BoundLogger real);
    o cast() torna explícito que o tipo de retorno é intencional, não
    um Any escapando sem querer.
    """
    return cast(structlog.BoundLogger, structlog.get_logger(name))
