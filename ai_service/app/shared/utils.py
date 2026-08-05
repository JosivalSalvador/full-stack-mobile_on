"""Utilitários genéricos usados por mais de um módulo do ai_service.

Concentra funções de propósito geral (extração de features de senha,
estimativa de consumo de tokens) que não pertencem à lógica de negócio
de um módulo específico em app/modules/.
"""

import re
from dataclasses import dataclass

_CHARS_PER_TOKEN_ESTIMATE = 4
_COMMON_KEYBOARD_SEQUENCES = (
    "qwerty",
    "asdfgh",
    "zxcvbn",
    "123456",
    "abcdef",
)
_SPECIAL_CHAR_PATTERN = re.compile(r"[^a-zA-Z0-9]")


@dataclass(frozen=True, slots=True)
class PasswordFeatures:
    """Features determinísticas extraídas de uma senha.

    Usadas tanto no treino (scripts/train.py, sobre o dataset RockYou)
    quanto na inferência (app/modules/vault_audit/pipeline.py, sobre
    uma senha individual) — o mesmo cálculo dos dois lados garante que
    o modelo ONNX vê, em produção, exatamente as features com que foi
    treinado.
    """

    length: int
    has_upper: bool
    has_lower: bool
    has_digit: bool
    has_special: bool
    unique_char_ratio: float
    has_keyboard_sequence: bool

    def to_vector(self) -> list[float]:
        """Converte as features para o vetor numérico esperado pelo ONNX."""
        return [
            float(self.length),
            float(self.has_upper),
            float(self.has_lower),
            float(self.has_digit),
            float(self.has_special),
            self.unique_char_ratio,
            float(self.has_keyboard_sequence),
        ]


def extract_password_features(password: str) -> PasswordFeatures:
    """Extrai as features determinísticas de uma senha.

    Não usa nenhuma biblioteca de terceiros: os cálculos são simples o
    bastante (comprimento, classes de caractere, razão de caracteres
    únicos, presença de sequência de teclado comum) para serem
    reimplementados diretamente, evitando uma dependência extra.
    """
    length = len(password)
    unique_char_ratio = len(set(password)) / length if length > 0 else 0.0
    lowered = password.lower()
    has_keyboard_sequence = any(
        sequence in lowered for sequence in _COMMON_KEYBOARD_SEQUENCES
    )

    return PasswordFeatures(
        length=length,
        has_upper=any(char.isupper() for char in password),
        has_lower=any(char.islower() for char in password),
        has_digit=any(char.isdigit() for char in password),
        has_special=bool(_SPECIAL_CHAR_PATTERN.search(password)),
        unique_char_ratio=unique_char_ratio,
        has_keyboard_sequence=has_keyboard_sequence,
    )


def estimate_token_count(text: str) -> int:
    """Estima o número de tokens de um texto por aproximação de caracteres.

    O Ollama não expõe um endpoint de tokenização, e a contagem exata
    depende do tokenizer específico do modelo carregado (ver
    OLLAMA_MODEL em app/core/config.py). Esta é uma aproximação
    (~4 caracteres por token) suficiente para métricas agregadas em
    app/api/v1/endpoints/metrics.py, não para controle rígido de
    limite de contexto.
    """
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)
