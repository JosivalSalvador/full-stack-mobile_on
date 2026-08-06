"""Ponto de entrada do Alembic para migrations do ai_service.

Baseado no template async oficial do Alembic, adaptado em dois
pontos: a URL de conexão vem de app.core.config.settings (não do
alembic.ini, que a deixa vazia de propósito) e target_metadata aponta
para SQLModel.metadata, já que app/modules/*/models.py define suas
tabelas via SQLModel, não via uma Base declarativa separada.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from alembic import context
from app.core.config import settings

# Importar os módulos de app/modules/*/models.py aqui é o que registra
# suas tabelas em SQLModel.metadata antes do autogenerate rodar. Sem
# este import, `alembic revision --autogenerate` não veria nenhuma
# tabela e geraria migrations vazias.
from app.modules.vault_audit import models as vault_audit_models  # noqa: F401

# Objeto de configuração do Alembic, dá acesso aos valores do .ini.
config = context.config

# Configura os loggers definidos nas seções [loggers]/[handlers]/
# [formatters] do alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadados usados pelo --autogenerate para comparar o estado do
# banco com o estado dos models Python e gerar a migration da
# diferença.
target_metadata = SQLModel.metadata


def get_url() -> str:
    """Resolve a URL de conexão a partir de app.core.config.settings.

    Não lê sqlalchemy.url do alembic.ini (que é deixado vazio de
    propósito): a URL real vive em DATABASE_URL no .env, única fonte
    de verdade também usada por app/core/database.py, evitando duas
    credenciais de banco que podem ficar dessincronizadas.
    """
    return settings.database_url


def run_migrations_offline() -> None:
    """Roda migrations em modo 'offline': gera SQL sem conectar no banco.

    Usado por `alembic upgrade head --sql`, útil para revisar o SQL
    antes de aplicar manualmente em um ambiente restrito.
    """
    context.configure(
        url=get_url(),
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


async def run_async_migrations() -> None:
    """Cria um engine assíncrono e associa a conexão ao contexto do Alembic.

    A URL é sobrescrita explicitamente aqui (não vem da seção lida do
    .ini) para garantir que o mesmo DATABASE_URL de app/core/config.py
    seja usado, mesmo que alembic.ini tenha sqlalchemy.url vazio.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Roda migrations em modo 'online': conecta de verdade no banco."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
