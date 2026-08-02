"""Fixtures compartilhadas por toda a suíte de testes unitários.

Nunca conecta no Postgres de desenvolvimento nem no Ollama real —
providers externos são substituídos por fakes. `integration_test`
(agora `tests/integration/`) propositalmente não usa esses fakes: usa
os providers reais, carregados de verdade no lifespan da aplicação.
"""

import pytest

from app.ml.providers.base import Provider
from app.ml.providers.external_llm import LLMExplanationRequest
from app.ml.providers.local_model import PasswordStrengthResult


class FakeLocalModel(Provider[str, PasswordStrengthResult]):
    """Fake do provider local: determinístico, sem rodar zxcvbn de verdade."""

    name = "fake_local"

    async def run(self, data: str) -> PasswordStrengthResult:
        is_weak = data.lower() in {"123456", "password", "senha123"}
        return PasswordStrengthResult(
            score=0 if is_weak else 4,
            warning="Esta é uma senha muito comum." if is_weak else "",
            suggestions=("Adicione mais palavras.",) if is_weak else (),
            crack_time_display="menos de um segundo" if is_weak else "séculos",
            is_weak=is_weak,
        )


class FakeExternalLLM(Provider[LLMExplanationRequest, str]):
    """Fake do provider externo: devolve texto fixo, sem chamar o Ollama."""

    name = "fake_external_llm"

    async def run(self, data: LLMExplanationRequest) -> str:
        return f"Explicação de teste para score {data.score}."


@pytest.fixture
def fake_local_model() -> FakeLocalModel:
    return FakeLocalModel()


@pytest.fixture
def fake_external_llm() -> FakeExternalLLM:
    return FakeExternalLLM()
