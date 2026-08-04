"""Modelo local: avalia a força de uma senha sem que ela saia do
processo.

Usa `zxcvbn` (biblioteca originada na Dropbox), que estima a
resistência de uma senha a ataques de força bruta usando padrões
reais de vazamentos, dicionários, substituição l33t e sequências de
teclado — mais realista que regras simples de "tem número e símbolo".

Importante: a senha em si nunca é logada, persistida, nem devolvida
neste módulo. Apenas os campos derivados (score, avisos, tempo
estimado de quebra) saem daqui.
"""

from dataclasses import dataclass

from zxcvbn import zxcvbn

from app.domain.common.ml_model import MLModel


@dataclass(frozen=True)
class PasswordStrengthResult:
    """Avaliação de força de uma senha, sem conter a senha em si."""

    score: int
    """De 0 (péssima) a 4 (ótima), escala do próprio zxcvbn."""

    warning: str
    """Aviso curto do zxcvbn sobre o padrão encontrado, se houver."""

    suggestions: tuple[str, ...]
    """Sugestões de melhoria geradas pelo zxcvbn."""

    crack_time_display: str
    """Tempo estimado de quebra em ataque offline, formato legível."""

    is_weak: bool
    """Atalho: True quando score <= 2 (considerada fraca)."""


class LocalPasswordModel(MLModel[str, PasswordStrengthResult]):
    """Modelo local que roda `zxcvbn` sobre uma senha."""

    _WEAK_SCORE_THRESHOLD = 2

    @property
    def name(self) -> str:
        return "local_zxcvbn"

    async def predict(self, data: str) -> PasswordStrengthResult:
        """Avalia `data` (a senha) e devolve o resultado sem a senha.

        `zxcvbn` é síncrono e roda em memória (sem I/O de rede ou
        disco), então chamá-lo diretamente aqui não bloqueia
        significativamente o event loop.
        """
        raw = zxcvbn(data)

        return PasswordStrengthResult(
            score=raw["score"],
            warning=raw["feedback"]["warning"],
            suggestions=tuple(raw["feedback"]["suggestions"]),
            crack_time_display=str(
                raw["crack_times_display"]["offline_slow_hashing_1e4_per_second"]
            ),
            is_weak=raw["score"] <= self._WEAK_SCORE_THRESHOLD,
        )
