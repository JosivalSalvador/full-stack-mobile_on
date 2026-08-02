"""Testes do provider local de avaliação de senha.

Roda o zxcvbn de verdade (não é mockado) — é um cálculo local, em
memória, sem I/O de rede, então rodá-lo em teste unitário não tem o
custo/instabilidade de uma chamada externa.
"""

import pytest

from app.ml.providers.local_model import LocalPasswordModel


@pytest.fixture
def model() -> LocalPasswordModel:
    return LocalPasswordModel()


class TestLocalPasswordModel:
    async def test_common_password_scores_low(self, model: LocalPasswordModel) -> None:
        result = await model.run("123456")

        assert result.score == 0
        assert result.is_weak is True

    async def test_complex_password_scores_high(
        self, model: LocalPasswordModel
    ) -> None:
        result = await model.run("x7$kP9#mQ2vL!nR4wZ8")

        assert result.score == 4
        assert result.is_weak is False

    async def test_password_never_leaks_into_result(
        self, model: LocalPasswordModel
    ) -> None:
        password = "MinhaSenhaSecretaUnica2026"

        result = await model.run(password)

        assert password not in str(result)

    async def test_provider_name(self, model: LocalPasswordModel) -> None:
        assert model.name == "local_zxcvbn"
