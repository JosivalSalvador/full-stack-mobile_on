"""Testes do VaultAuditService.

O repository é substituído por um fake em memória — o que está sob
teste aqui é a ORQUESTRAÇÃO do service (chamar o pipeline, montar os
records, calcular weak_count, montar a resposta), não a persistência
real (isso já é coberto em test_repository.py).
"""

from app.modules.vault_audit.models import VaultItemAuditRecord
from app.modules.vault_audit.repositories.repository import VaultAuditRepository
from app.modules.vault_audit.schemas import VaultAuditRequest, VaultItemInput
from app.modules.vault_audit.service import VaultAuditService
from tests.conftest import FakeExternalLLM, FakeLocalModel


class FakeVaultAuditRepository(VaultAuditRepository):
    """Fake em memória: guarda os records salvos, sem tocar banco."""

    def __init__(self) -> None:
        self.saved: list[VaultItemAuditRecord] = []

    async def save_many(
        self, records: list[VaultItemAuditRecord]
    ) -> list[VaultItemAuditRecord]:
        self.saved.extend(records)
        return records

    async def list_by_user(self, user_id: str) -> list[VaultItemAuditRecord]:
        return [r for r in self.saved if r.user_id == user_id]


class TestVaultAuditService:
    async def test_run_audit_persists_all_items(
        self,
        fake_local_model: FakeLocalModel,
        fake_external_llm: FakeExternalLLM,
    ) -> None:
        repository = FakeVaultAuditRepository()
        service = VaultAuditService(repository, fake_local_model, fake_external_llm)
        request = VaultAuditRequest(
            user_id="user-1",
            items=[
                VaultItemInput(item_id="a", password="123456"),
                VaultItemInput(item_id="b", password="x7$kP9#mQ2vL!nR4wZ8"),
            ],
        )

        await service.run_audit(request)

        assert len(repository.saved) == 2
        assert {r.item_id for r in repository.saved} == {"a", "b"}

    async def test_run_audit_computes_weak_count(
        self,
        fake_local_model: FakeLocalModel,
        fake_external_llm: FakeExternalLLM,
    ) -> None:
        repository = FakeVaultAuditRepository()
        service = VaultAuditService(repository, fake_local_model, fake_external_llm)
        request = VaultAuditRequest(
            user_id="user-1",
            items=[
                VaultItemInput(item_id="a", password="123456"),
                VaultItemInput(item_id="b", password="password"),
                VaultItemInput(item_id="c", password="x7$kP9#mQ2vL!nR4wZ8"),
            ],
        )

        response = await service.run_audit(request)

        assert response.weak_count == 2

    async def test_run_audit_response_matches_request_user(
        self,
        fake_local_model: FakeLocalModel,
        fake_external_llm: FakeExternalLLM,
    ) -> None:
        repository = FakeVaultAuditRepository()
        service = VaultAuditService(repository, fake_local_model, fake_external_llm)
        request = VaultAuditRequest(
            user_id="user-42",
            items=[VaultItemInput(item_id="a", password="123456")],
        )

        response = await service.run_audit(request)

        assert response.user_id == "user-42"
        assert len(response.items) == 1

    async def test_run_audit_password_never_leaks_into_response(
        self,
        fake_local_model: FakeLocalModel,
        fake_external_llm: FakeExternalLLM,
    ) -> None:
        repository = FakeVaultAuditRepository()
        service = VaultAuditService(repository, fake_local_model, fake_external_llm)
        password = "SenhaSuperSecretaDeTeste"
        request = VaultAuditRequest(
            user_id="user-1",
            items=[VaultItemInput(item_id="a", password=password)],
        )

        response = await service.run_audit(request)

        assert password not in response.model_dump_json()
