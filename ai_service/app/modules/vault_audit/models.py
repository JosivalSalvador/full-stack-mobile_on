from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class VaultItemAuditRecord(SQLModel, table=True):
    """Um registro de auditoria para um único item do vault."""

    __tablename__ = "vault_item_audits"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    user_id: str = Field(index=True)
    """Identificador do usuário dono do vault auditado."""

    item_id: str = Field(index=True)
    """Identificador do item do vault (a senha em si nunca é salva)."""

    score: int
    """De 0 (péssima) a 4 (ótima), escala do zxcvbn."""

    is_weak: bool
    warning: str
    crack_time_display: str

    explanation: str | None = Field(default=None)
    """Texto gerado pelo provider externo. None quando esse provider
    falhou naquela execução — o score continua válido mesmo assim."""

    audited_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), index=True),
    )
