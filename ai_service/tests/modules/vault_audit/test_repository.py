"""Testes do repository de auditoria de vault.

Roda contra o Postgres de TESTE de verdade (porta 5433, via
`test_db_session` em conftest.py) — não é mockado, porque o que está
sob teste aqui é justamente a tradução correta entre objeto Python e
linha de banco.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vault_audit.models import VaultItemAuditRecord
from app.modules.vault_audit.repositories.repository_impl import (
    SqlVaultAuditRepository,
)


def make_record(user_id: str, item_id: str, score: int = 2) -> VaultItemAuditRecord:
    return VaultItemAuditRecord(
        user_id=user_id,
        item_id=item_id,
        score=score,
        is_weak=score <= 2,
        warning="",
        crack_time_display="1 dia",
        explanation=None,
        audited_at=datetime.now(UTC),
    )


class TestSqlVaultAuditRepository:
    async def test_save_many_persists_records(
        self, test_db_session: AsyncSession
    ) -> None:
        repository = SqlVaultAuditRepository(test_db_session)
        records = [make_record("user-1", "item-a"), make_record("user-1", "item-b")]

        saved = await repository.save_many(records)

        assert len(saved) == 2
        assert all(record.id is not None for record in saved)

    async def test_list_by_user_returns_only_that_users_records(
        self, test_db_session: AsyncSession
    ) -> None:
        repository = SqlVaultAuditRepository(test_db_session)
        await repository.save_many(
            [
                make_record("user-1", "item-a"),
                make_record("user-2", "item-b"),
            ]
        )

        results = await repository.list_by_user("user-1")

        assert len(results) == 1
        assert results[0].user_id == "user-1"

    async def test_list_by_user_orders_most_recent_first(
        self, test_db_session: AsyncSession
    ) -> None:
        repository = SqlVaultAuditRepository(test_db_session)
        older = make_record("user-1", "item-old")
        older.audited_at = datetime(2020, 1, 1, tzinfo=UTC)
        newer = make_record("user-1", "item-new")
        newer.audited_at = datetime(2026, 1, 1, tzinfo=UTC)

        await repository.save_many([older, newer])

        results = await repository.list_by_user("user-1")

        assert results[0].item_id == "item-new"
        assert results[1].item_id == "item-old"

    async def test_list_by_user_with_no_records_returns_empty(
        self, test_db_session: AsyncSession
    ) -> None:
        repository = SqlVaultAuditRepository(test_db_session)

        results = await repository.list_by_user("user-sem-historico")

        assert results == []
