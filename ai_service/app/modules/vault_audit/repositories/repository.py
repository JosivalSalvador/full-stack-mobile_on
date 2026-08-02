"""Interface de acesso a dados da auditoria de vault.

Define o que é possível fazer com os registros de auditoria, sem
dizer como — a implementação concreta (Postgres, via SQLAlchemy) fica
em `repository_impl.py`. `service.py` depende apenas desta interface,
nunca da implementação, o que permite trocar a forma de persistência
sem tocar na regra de negócio.
"""

from abc import ABC, abstractmethod

from app.modules.vault_audit.models import VaultItemAuditRecord


class VaultAuditRepository(ABC):
    """Porta de acesso a dados para registros de auditoria de vault."""

    @abstractmethod
    async def save_many(
        self, records: list[VaultItemAuditRecord]
    ) -> list[VaultItemAuditRecord]:
        """Persiste `records` e devolve as instâncias já salvas."""
        ...

    @abstractmethod
    async def list_by_user(self, user_id: str) -> list[VaultItemAuditRecord]:
        """Devolve todo o histórico de auditorias de `user_id`, mais
        recente primeiro."""
        ...
