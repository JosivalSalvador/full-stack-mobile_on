"""Testes do pipeline de auditoria de vault.

Usa os fakes de `tests/conftest.py` para os dois providers — o que
está sob teste aqui é a ORQUESTRAÇÃO (ordem, combinação, resiliência
a falha), não o comportamento interno de cada provider (isso já é
coberto em test_local_model.py e test_external_llm.py).
"""

from app.ml.pipelines.vault_audit_pipeline import audit_vault, audit_vault_item
from app.ml.providers.external_llm import LLMExplanationRequest, LLMProviderError
from tests.conftest import FakeExternalLLM, FakeLocalModel


class FailingExternalLLM(FakeExternalLLM):
    """Fake que sempre falha, para testar resiliência do pipeline."""

    name = "failing_external_llm"

    async def run(self, data: LLMExplanationRequest) -> str:
        raise LLMProviderError("falha simulada")


class TestAuditVaultItem:
    async def test_combines_local_and_external_results(
        self,
        fake_local_model: FakeLocalModel,
        fake_external_llm: FakeExternalLLM,
    ) -> None:
        result = await audit_vault_item(
            "item-1",
            "123456",
            local_model=fake_local_model,
            external_llm=fake_external_llm,
        )

        assert result.item_id == "item-1"
        assert result.strength.score == 0
        assert result.explanation is not None

    async def test_password_never_leaks_into_result(
        self,
        fake_local_model: FakeLocalModel,
        fake_external_llm: FakeExternalLLM,
    ) -> None:
        password = "SenhaSuperSecretaDeTeste"

        result = await audit_vault_item(
            "item-1",
            password,
            local_model=fake_local_model,
            external_llm=fake_external_llm,
        )

        assert password not in str(result)

    async def test_external_llm_failure_does_not_discard_audit(
        self, fake_local_model: FakeLocalModel
    ) -> None:
        result = await audit_vault_item(
            "item-1",
            "123456",
            local_model=fake_local_model,
            external_llm=FailingExternalLLM(),
        )

        assert result.strength.score == 0
        assert result.explanation is None


class TestAuditVault:
    async def test_audits_every_item_independently(
        self,
        fake_local_model: FakeLocalModel,
        fake_external_llm: FakeExternalLLM,
    ) -> None:
        items = {"a": "123456", "b": "x7$kP9#mQ2vL!nR4wZ8", "c": "password"}

        results = await audit_vault(
            items,
            local_model=fake_local_model,
            external_llm=fake_external_llm,
        )

        assert len(results) == 3
        assert {r.item_id for r in results} == {"a", "b", "c"}

    async def test_one_item_failing_does_not_affect_others(
        self, fake_local_model: FakeLocalModel
    ) -> None:
        items = {"a": "123456", "b": "outrasenha"}

        results = await audit_vault(
            items,
            local_model=fake_local_model,
            external_llm=FailingExternalLLM(),
        )

        assert len(results) == 2
        assert all(r.explanation is None for r in results)
        assert all(r.strength.score is not None for r in results)
