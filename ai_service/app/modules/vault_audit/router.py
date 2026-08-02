"""Rota HTTP da auditoria de vault.

Monta o `VaultAuditService` a partir das dependências do FastAPI
(sessão de banco, providers já carregados no startup) e delega toda a
regra de negócio a ele — o router não decide nada além de formato de
requisição/resposta e código de status HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.ml.model_loader import get_external_llm, get_local_model
from app.ml.providers.external_llm import ExternalLLMProvider
from app.ml.providers.local_model import LocalPasswordModel
from app.modules.vault_audit.repositories.repository_impl import (
    SqlVaultAuditRepository,
)
from app.modules.vault_audit.schemas import VaultAuditRequest, VaultAuditResponse
from app.modules.vault_audit.service import VaultAuditService

router = APIRouter(prefix="/vault-audit", tags=["vault-audit"])


def get_vault_audit_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    local_model: Annotated[LocalPasswordModel, Depends(get_local_model)],
    external_llm: Annotated[ExternalLLMProvider, Depends(get_external_llm)],
) -> VaultAuditService:
    """Monta um `VaultAuditService` com as dependências desta requisição."""
    repository = SqlVaultAuditRepository(session)
    return VaultAuditService(repository, local_model, external_llm)


@router.post("")
async def audit_vault(
    request: VaultAuditRequest,
    service: Annotated[VaultAuditService, Depends(get_vault_audit_service)],
) -> VaultAuditResponse:
    """Audita todas as senhas de `request.items` e persiste o resultado.

    O `backend` (Go) é responsável por autenticar o usuário antes de
    chamar esta rota; `request.user_id` é aceito como já validado.
    """
    return await service.run_audit(request)
