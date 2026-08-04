"""Carrega o modelo local uma única vez, no startup do processo.

Instanciar `LocalPasswordModel` tem custo pequeno mas não nulo (o
zxcvbn carrega listas internas de dicionário na primeira chamada).
Fazer isso a cada request desperdiça esse custo repetidamente.

`main.py` chama `load_model()` uma vez no lifespan da aplicação;
rotas e services pedem o modelo já pronto via `get_local_model()`.
"""

from app.infrastructure.ml_models.local_model import LocalPasswordModel

_local_model: LocalPasswordModel | None = None


def load_model() -> None:
    """Instancia o modelo local. Chamar uma única vez, no startup."""
    global _local_model
    _local_model = LocalPasswordModel()


def get_local_model() -> LocalPasswordModel:
    """Devolve a instância única do modelo local.

    Levanta `RuntimeError` se chamado antes de `load_model()` — isso
    pega, em desenvolvimento, o erro de esquecer de inicializar o
    modelo no lifespan da aplicação.
    """
    if _local_model is None:
        raise RuntimeError(
            "Modelo local ainda não foi carregado. "
            "Chame load_model() no startup da aplicação."
        )
    return _local_model
