"""Regra de negócio da auditoria de vault.

Conecta as três camadas já construídas: recebe a requisição da API
(`schemas.py`), aciona o pipeline de IA (`app.ml.pipelines`), persiste
o resultado via repository (`repositories/`), e devolve a resposta já
no formato da API.

Não importa FastAPI nem SQLAlchemy diretamente — depende apenas da
interface `VaultAuditRepository` e das funções do pipeline, o que
mantém este módulo testável sem precisar de servidor HTTP nem banco
real.
"""

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.ml.pipelines.vault_audit_pipeline import audit_vault
from app.ml.providers.external_llm import ExternalLLMProvider
from app.ml.providers.local_model import LocalPasswordModel
from app.modules.vault_audit.models import VaultItemAuditRecord
from app.modules.vault_audit.repositories.repository import VaultAuditRepository
from app.modules.vault_audit.schemas import (
    VaultAuditRequest,
    VaultAuditResponse,
    VaultItemAuditResponse,
)

logger = get_logger(__name__)


class VaultAuditService:
    """Orquestra a auditoria de um vault: IA, persistência, resposta."""

    def __init__(
        self,
        repository: VaultAuditRepository,
        local_model: LocalPasswordModel,
        external_llm: ExternalLLMProvider,
    ) -> None:
        self._repository = repository
        self._local_model = local_model
        self._external_llm = external_llm

    async def run_audit(self, request: VaultAuditRequest) -> VaultAuditResponse:
        """Executa a auditoria completa de `request.items` e persiste
        o resultado.
        """
        logger.info(
            "vault_audit_started",
            user_id=request.user_id,
            item_count=len(request.items),
        )

        passwords_by_item = {item.item_id: item.password for item in request.items}

        audits = await audit_vault(
            passwords_by_item,
            local_model=self._local_model,
            external_llm=self._external_llm,
        )

        audited_at = datetime.now(UTC)
        records = [
            VaultItemAuditRecord(
                user_id=request.user_id,
                item_id=audit.item_id,
                score=audit.strength.score,
                is_weak=audit.strength.is_weak,
                warning=audit.strength.warning,
                crack_time_display=audit.strength.crack_time_display,
                explanation=audit.explanation,
                audited_at=audited_at,
            )
            for audit in audits
        ]

        await self._repository.save_many(records)

        weak_count = sum(1 for record in records if record.is_weak)
        logger.info(
            "vault_audit_completed",
            user_id=request.user_id,
            weak_count=weak_count,
        )

        return VaultAuditResponse(
            user_id=request.user_id,
            audited_at=audited_at,
            weak_count=weak_count,
            items=[
                VaultItemAuditResponse(
                    item_id=record.item_id,
                    score=record.score,
                    is_weak=record.is_weak,
                    warning=record.warning,
                    crack_time_display=record.crack_time_display,
                    explanation=record.explanation,
                )
                for record in records
            ],
        )
