"""Testes de `model_loader`: instância única dos providers por processo.

`_local_model` e `_external_llm` são estado global do módulo — por
isso a fixture `reset_providers_state` garante que cada teste comece
do zero, sem vazar o estado de um teste para o próximo.
"""

import pytest

from app.ml import model_loader
from app.ml.providers.external_llm import ExternalLLMProvider
from app.ml.providers.local_model import LocalPasswordModel


@pytest.fixture(autouse=True)
def reset_providers_state() -> None:
    """Reseta as globais do module antes de cada teste desta suíte."""
    model_loader._local_model = None
    model_loader._external_llm = None


class TestGetLocalModel:
    def test_raises_before_load_providers(self) -> None:
        with pytest.raises(RuntimeError, match="load_providers"):
            model_loader.get_local_model()

    def test_returns_instance_after_load_providers(self) -> None:
        model_loader.load_providers()

        result = model_loader.get_local_model()

        assert isinstance(result, LocalPasswordModel)


class TestGetExternalLLM:
    def test_raises_before_load_providers(self) -> None:
        with pytest.raises(RuntimeError, match="load_providers"):
            model_loader.get_external_llm()

    def test_returns_instance_after_load_providers(self) -> None:
        model_loader.load_providers()

        result = model_loader.get_external_llm()

        assert isinstance(result, ExternalLLMProvider)


class TestLoadProviders:
    def test_same_instance_returned_across_calls(self) -> None:
        """`load_providers` roda uma vez por processo — chamadas
        subsequentes a `get_local_model`/`get_external_llm` devem
        devolver a mesma instância, não uma nova a cada vez.
        """
        model_loader.load_providers()

        assert model_loader.get_local_model() is model_loader.get_local_model()
        assert model_loader.get_external_llm() is model_loader.get_external_llm()
