"""Testes de `reaudit_vault_on_leak_update`.

`db_session_context()` conecta na URL de `core.config` (que aponta
para o banco de DEV por padrão) — por isso este teste usa
`monkeypatch` para trocar temporariamente `async_session_factory` de
`core.database` pela sessão de teste, em vez de deixar a função tocar
o banco de dev de verdade.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml import model_loader
from app.workers.background_tasks import reaudit_vault_on_leak_update


@pytest.fixture(autouse=True)
def _use_test_session(
    monkeypatch: pytest.MonkeyPatch, test_db_session: AsyncSession
) -> None:
    """Faz `db_session_context()` (usado dentro da tarefa) devolver a
    sessão de teste, em vez de abrir uma conexão nova com o banco de
    dev configurado em `core.config`.
    """

    @asynccontextmanager
    async def fake_db_session_context() -> AsyncGenerator[AsyncSession]:
        yield test_db_session

    monkeypatch.setattr(
        "app.workers.background_tasks.db_session_context",
        fake_db_session_context,
    )


@pytest.fixture(autouse=True)
def _load_fake_providers(
    monkeypatch: pytest.MonkeyPatch, fake_local_model, fake_external_llm
) -> None:
    """Faz `get_local_model()`/`get_external_llm()` (chamados dentro
    da tarefa) devolverem os fakes, em vez de exigir
    `load_providers()` já ter rodado com os providers reais.
    """
    monkeypatch.setattr(model_loader, "_local_model", fake_local_model)
    monkeypatch.setattr(model_loader, "_external_llm", fake_external_llm)


class TestReauditVaultOnLeakUpdate:
    async def test_updates_dictionary_and_persists_new_audit(
        self, test_db_session: AsyncSession
    ) -> None:
        from sqlalchemy import select

        from app.modules.vault_audit.models import VaultItemAuditRecord

        await reaudit_vault_on_leak_update(
            user_id="worker-user",
            items={"a": "123456", "b": "outrasenha"},
            leaked_passwords=["senha-vazada-de-teste"],
        )

        result = await test_db_session.execute(
            select(VaultItemAuditRecord).where(
                VaultItemAuditRecord.user_id == "worker-user"
            )
        )
        records = result.scalars().all()

        assert len(records) == 2
