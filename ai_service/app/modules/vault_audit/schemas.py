"""Formato de entrada e saída da API de auditoria de vault.

Estes são os contratos Pydantic que a rota HTTP expõe — diferentes
dos modelos de banco (`models.py`) e dos tipos internos do pipeline
de IA (`app/ml/pipelines/vault_audit_pipeline.py`). Nenhum deles
carrega a senha em texto puro para fora do processo.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class VaultItemInput(BaseModel):
    """Um item do vault a ser auditado."""

    item_id: str
    password: str = Field(
        repr=False,
        description="Nunca é logada, persistida, nem incluída em erro.",
    )


class VaultAuditRequest(BaseModel):
    """Corpo da requisição: o vault inteiro de um usuário."""

    user_id: str
    items: list[VaultItemInput]


class VaultItemAuditResponse(BaseModel):
    """Resultado da auditoria de um único item, devolvido pela API."""

    item_id: str
    score: int
    is_weak: bool
    warning: str
    crack_time_display: str
    explanation: str | None


class VaultAuditResponse(BaseModel):
    """Corpo da resposta: resultado da auditoria de todo o vault."""

    user_id: str
    audited_at: datetime
    items: list[VaultItemAuditResponse]
    weak_count: int
