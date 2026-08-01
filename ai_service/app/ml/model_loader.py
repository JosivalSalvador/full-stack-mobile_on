"""Carrega os providers de IA uma única vez, no startup do processo.

Regra de ouro de serviços de IA: instanciar um provider tem custo (o
`LocalPasswordModel` carrega listas internas do zxcvbn; o
`ExternalLLMProvider` abre um client HTTP com pool de conexões).
Fazer isso a cada request desperdiça esse custo a cada chamada e, no
caso do client HTTP, evita reaproveitar conexões abertas.

Este módulo garante instância única por processo. `main.py` chama
`load_providers()` uma vez no lifespan da aplicação; rotas e services
pedem os providers já prontos via `get_local_model()` /
`get_external_llm()`.
"""

from app.ml.providers.external_llm import ExternalLLMProvider
from app.ml.providers.local_model import LocalPasswordModel

_local_model: LocalPasswordModel | None = None
_external_llm: ExternalLLMProvider | None = None


def load_providers() -> None:
    """Instancia todos os providers. Chamar uma única vez, no startup."""
    global _local_model, _external_llm
    _local_model = LocalPasswordModel()
    _external_llm = ExternalLLMProvider()


def get_local_model() -> LocalPasswordModel:
    """Devolve a instância única do provider local.

    Levanta `RuntimeError` se chamado antes de `load_providers()` —
    isso pega, em desenvolvimento, o erro de esquecer de inicializar
    os providers no lifespan da aplicação.
    """
    if _local_model is None:
        raise RuntimeError(
            "Providers ainda não foram carregados. "
            "Chame load_providers() no startup da aplicação."
        )
    return _local_model


def get_external_llm() -> ExternalLLMProvider:
    """Devolve a instância única do provider de LLM externo.

    Mesma regra de `get_local_model()`: exige `load_providers()` ter
    rodado antes.
    """
    if _external_llm is None:
        raise RuntimeError(
            "Providers ainda não foram carregados. "
            "Chame load_providers() no startup da aplicação."
        )
    return _external_llm
