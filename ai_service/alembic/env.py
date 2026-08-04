"""Configuração do Alembic para este serviço.

Usa o mesmo engine assíncrono de `app.core.database`, em vez do
engine síncrono que o template padrão do Alembic gera — para não
manter duas formas diferentes (síncrona e assíncrona) de conectar ao
mesmo banco dentro do projeto.

`target_metadata` aponta para os metadados do SQLModel, que agregam
automaticamente toda tabela declarada em qualquer `models.py` do
projeto, desde que o módulo tenha sido importado (ver a lista de
imports logo abaixo).
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from alembic import context
from app.core.config import get_settings

# Importa cada `models.py` do projeto para que suas tabelas sejam
# registradas em `SQLModel.metadata` antes do autogenerate rodar.
from ai_service.app.domain.vault_audit.models import VaultItemAuditRecord  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Gera SQL sem se conectar ao banco (modo `--sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Conecta ao banco de verdade e aplica as migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
