"""Testes de `train`: atualização do dicionário de senhas vazadas.

Roda o zxcvbn de verdade (não é mockado) — o que está sob teste aqui é
justamente o efeito real de `add_frequency_lists` sobre o resultado
que `LocalPasswordModel` devolve.
"""

from app.ml.providers.local_model import LocalPasswordModel
from app.ml.train import update_leaked_passwords_dictionary


class TestUpdateLeakedPasswordsDictionary:
    async def test_password_added_to_dictionary_scores_lower(self) -> None:
        model = LocalPasswordModel()
        password = "MinhaSenhaCorporativaXYZ2026"

        before = await model.run(password)

        update_leaked_passwords_dictionary([password.lower()])

        after = await model.run(password)

        assert after.score < before.score
        assert after.is_weak is True

    async def test_calling_again_replaces_previous_list(self) -> None:
        first_password = "PrimeiraListaDeVazamento2026"
        second_password = "SegundaListaDeVazamento2026"

        update_leaked_passwords_dictionary([first_password.lower()])
        update_leaked_passwords_dictionary([second_password.lower()])

        model = LocalPasswordModel()
        result = await model.run(second_password)

        assert result.is_weak is True
