"""Configuração de log estruturado do ai_service.

Usa structlog para produzir logs como dados estruturados (chave/valor),
não texto solto. Em produção, sai como JSON (consumível por ferramentas
de observabilidade); em desenvolvimento, sai como texto colorido,
legível no terminal.

FastAPI e Uvicorn usam o módulo `logging` padrão do Python por baixo.
Por isso o pipeline do structlog é roteado através dele (via
`ProcessorFormatter`), garantindo que logs de bibliotecas de terceiro
saiam no mesmo formato dos logs escritos pelo próprio serviço.
"""

import logging
import sys
from typing import cast

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configura o structlog e o logging padrão do processo.

    Deve ser chamada uma única vez, no início da aplicação (em
    `main.py`, antes de qualquer outra coisa ser importada que possa
    emitir log).
    """
    settings = get_settings()

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: structlog.typing.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level)

    # Bibliotecas barulhentas: reduzimos o nível delas especificamente,
    # sem abafar o resto da aplicação.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str = "") -> structlog.stdlib.BoundLogger:
    """Retorna um logger vinculado ao módulo chamador.

    Uso:
        logger = get_logger(__name__)
        logger.info("vault_audit_started", user_id=user_id, item_count=80)
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
