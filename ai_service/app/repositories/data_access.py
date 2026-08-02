"""Acesso a dados compartilhado, não vinculado a nenhum módulo de
negócio específico.

Hoje cobre a verificação de saúde do banco de dados, usada tanto pela
rota de health check da aplicação (`main.py`) quanto por qualquer
worker que precise confirmar que o banco está acessível antes de
iniciar um trabalho pesado (ver `workers/background_tasks.py`).

Módulos futuros que precisem de acesso a dado genérico, reutilizável
por mais de um domínio de negócio, também pertencem aqui.
"""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


async def is_database_healthy(session: AsyncSession) -> bool:
    """Confirma que `session` consegue executar uma query simples."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
