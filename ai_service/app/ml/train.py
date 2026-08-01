"""Atualiza o dicionário de senhas conhecidas do provider local.

`zxcvbn` não é um modelo treinado no sentido tradicional (não há
gradiente, não há pesos ajustados por época) — ele pontua uma senha
comparando-a contra dicionários de padrões conhecidos (senhas
vazadas, nomes, palavras comuns). O equivalente a "retreinar" este
provider é atualizar esses dicionários com novas listas de senhas
vazadas conhecidas.

Isso é feito via `zxcvbn.matching.add_frequency_lists`, que recebe um
dicionário no formato `{nome_da_lista: [senha, senha, ...]}` e o
compila para o índice interno (`RANKED_DICTIONARIES`) que o `zxcvbn()`
de fato consulta a cada chamada.

Este módulo deve ser chamado uma vez, no startup — antes de
`load_providers()` em `model_loader.py` — sempre que uma nova lista de
senhas vazadas estiver disponível.
"""

from zxcvbn.matching import add_frequency_lists

from app.core.logging import get_logger

logger = get_logger(__name__)


def update_leaked_passwords_dictionary(leaked_passwords: list[str]) -> None:
    """Registra `leaked_passwords` como um dicionário adicional que o
    provider local passa a reconhecer como senhas fracas conhecidas.

    Chamar novamente com uma lista mais recente substitui a anterior
    (mesma chave de dicionário); não acumula duplicatas entre chamadas.
    """
    add_frequency_lists({"leaked_passwords": leaked_passwords})
    logger.info(
        "leaked_passwords_dictionary_updated",
        entry_count=len(leaked_passwords),
    )
