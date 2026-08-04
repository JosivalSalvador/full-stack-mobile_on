"""Tarefas em segundo plano, fora do caminho de resposta de uma request.

Usa `BackgroundTasks` do próprio FastAPI: a tarefa roda no mesmo
processo, depois da resposta HTTP já ter sido enviada ao cliente. Não
sobrevive a um reinício do processo — para o volume de trabalho deste
exemplo (reavaliar um vault quando uma lista de senhas vazadas é
atualizada), isso é suficiente e evita a complexidade operacional de
uma fila externa (Redis, Celery), que exigiria infraestrutura própria
para rodar de graça.

Se um dia o volume justificar sobreviver a reinício e escalar workers
horizontalmente, esta função é o ponto de partida a substituir por uma
fila de verdade — o corpo da tarefa (chamar o service) não muda.
"""

from ai_service.app.core.db import db_session_context
from app.core.logging import get_logger
from app.ml.model_loader import get_external_llm, get_local_model
from app.ml.train import update_leaked_passwords_dictionary
from app.modules.vault_audit.repositories.repository_impl import (
    SqlVaultAuditRepository,
)
from ai_service.app.domain.vault_audit.schemas import VaultAuditRequest, VaultItemInput
from ai_service.app.domain.vault_audit.service import VaultAuditService

logger = get_logger(__name__)


async def reaudit_vault_on_leak_update(
    user_id: str,
    items: dict[str, str],
    leaked_passwords: list[str],
) -> None:
    """Atualiza o dicionário de senhas vazadas e reaudita `items`.

    Roda em segundo plano: quem chamou já recebeu resposta HTTP antes
    desta função começar a executar.
    """
    logger.info(
        "vault_reaudit_started",
        user_id=user_id,
        item_count=len(items),
        leaked_entry_count=len(leaked_passwords),
    )

    update_leaked_passwords_dictionary(leaked_passwords)

    async with db_session_context() as session:
        repository = SqlVaultAuditRepository(session)
        service = VaultAuditService(
            repository,
            get_local_model(),
            get_external_llm(),
        )

        request = VaultAuditRequest(
            user_id=user_id,
            items=[
                VaultItemInput(item_id=item_id, password=password)
                for item_id, password in items.items()
            ],
        )

        response = await service.run_audit(request)

    logger.info(
        "vault_reaudit_completed",
        user_id=user_id,
        weak_count=response.weak_count,
    )
