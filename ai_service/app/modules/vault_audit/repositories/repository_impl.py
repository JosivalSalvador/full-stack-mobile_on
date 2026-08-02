"""Implementação concreta do acesso a dados da auditoria de vault.

Usa a sessão assíncrona de `app.core.database` para persistir e
consultar `VaultItemAuditRecord` no Postgres. Esta é a única camada
do módulo que importa SQLAlchemy diretamente — o resto (service,
router) depende apenas da interface em `repository.py`.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vault_audit.models import VaultItemAuditRecord
from app.modules.vault_audit.repositories.repository import VaultAuditRepository


class SqlVaultAuditRepository(VaultAuditRepository):
    """Implementação via Postgres/SQLAlchemy da porta `VaultAuditRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(
        self, records: list[VaultItemAuditRecord]
    ) -> list[VaultItemAuditRecord]:
        self._session.add_all(records)
        await self._session.commit()
        for record in records:
            await self._session.refresh(record)
        return records

    async def list_by_user(self, user_id: str) -> list[VaultItemAuditRecord]:
        statement = (
            select(VaultItemAuditRecord)
            .where(VaultItemAuditRecord.user_id == user_id)
            .order_by(VaultItemAuditRecord.audited_at.desc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
