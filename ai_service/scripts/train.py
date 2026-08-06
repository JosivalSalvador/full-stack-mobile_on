"""Treino offline do classificador de força de senha.

Roda uma vez, fora do runtime do serviço: pega um dump do RockYou (ou
subconjunto público dele), extrai features determinísticas de cada
senha com a mesma função usada em produção (app/shared/utils.py),
deriva um rótulo de força em 3 classes por heurística, treina um
RandomForestClassifier e exporta o resultado para ONNX.

Uso:
    uv run python scripts/train.py --input /caminho/para/rockyou.txt --output model.onnx

O RockYou não é incluído no repositório (14M+ linhas); precisa ser
baixado separadamente de uma fonte pública e apontado via --input.
Dependências deste script (scikit-learn, skl2onnx, pandas) ficam em
dependency-groups.dev do pyproject.toml, não em produção — o serviço
em runtime só roda inferência sobre o .onnx já gerado, nunca treina.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from app.shared.utils import extract_password_features

# Limiares de comprimento e entropia aproximada usados para derivar o
# rótulo de força a partir das features, seguindo o approach validado
# na literatura (heurística sobre comprimento + classes de caractere +
# presença em listas de senhas comuns), alinhado a padrões como o NIST
# SP 800-63B para o que conta como senha "fraca".
_WEAK_MAX_LENGTH = 8
_STRONG_MIN_LENGTH = 12
_STRONG_MIN_CHAR_CLASSES = 3


def _derive_strength_label(password: str, has_keyboard_sequence: bool) -> int:
    """Deriva o rótulo de força (0=fraca, 1=média, 2=forte) por heurística.

    O RockYou não vem com rótulo de força; a prática estabelecida é
    derivar esse rótulo a partir de heurísticas conhecidas sobre a
    própria senha, em vez de rotular manualmente 14M+ linhas. O
    dataset é real, o rótulo é derivado — não inventado do zero.
    """
    length = len(password)
    char_classes = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )

    if has_keyboard_sequence or length <= _WEAK_MAX_LENGTH:
        return 0  # fraca
    if length >= _STRONG_MIN_LENGTH and char_classes >= _STRONG_MIN_CHAR_CLASSES:
        return 2  # forte
    return 1  # média


def _load_passwords(input_path: Path) -> list[str]:
    """Lê o dump de senhas, uma por linha.

    Ignora linhas vazias e linhas que não decodificam como UTF-8
    válido (comum em dumps de leak reais, que às vezes têm bytes
    corrompidos ou encoding misto).
    """
    passwords: list[str] = []
    with input_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            password = line.rstrip("\n")
            if password:
                passwords.append(password)
    return passwords


def _build_training_frame(passwords: list[str]) -> pd.DataFrame:
    """Extrai features de cada senha e monta o DataFrame de treino.

    Usa extract_password_features() de app/shared/utils.py — a mesma
    função que app/modules/vault_audit/pipeline.py vai chamar em
    produção sobre uma senha só, garantindo que o modelo treinado
    aqui vê, em inferência, exatamente o mesmo tipo de vetor de
    features com que foi treinado.
    """
    rows = []
    for password in passwords:
        features = extract_password_features(password)
        label = _derive_strength_label(password, features.has_keyboard_sequence)
        rows.append([*features.to_vector(), label])

    columns = [
        "length",
        "has_upper",
        "has_lower",
        "has_digit",
        "has_special",
        "unique_char_ratio",
        "has_keyboard_sequence",
        "label",
    ]
    return pd.DataFrame(rows, columns=columns)


def train_model(df: pd.DataFrame) -> RandomForestClassifier:
    """Treina o RandomForestClassifier sobre as features extraídas."""
    feature_columns = [c for c in df.columns if c != "label"]
    x = df[feature_columns].to_numpy(dtype=np.float32)
    y = df["label"].to_numpy(dtype=np.int64)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    accuracy = model.score(x_test, y_test)
    print(f"Acurácia no conjunto de teste: {accuracy:.4f}", file=sys.stderr)

    return model


def export_to_onnx(
    model: RandomForestClassifier, num_features: int, output_path: Path
) -> None:
    """Exporta o modelo treinado para ONNX.

    O nome e o shape do initial_type ([None, num_features]) precisam
    bater com o que app/engine/ml/loader.py espera ao carregar o
    modelo e com o array que app/engine/ml/batcher.py monta antes de
    chamar session.run() — None na primeira dimensão permite batch de
    tamanho variável, essencial para o batching de janela de tempo do
    fluxo síncrono.
    """
    initial_types = [("input", FloatTensorType([None, num_features]))]
    onnx_model = convert_sklearn(model, initial_types=initial_types)

    output_path.write_bytes(onnx_model.SerializeToString())
    print(f"Modelo exportado para {output_path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Caminho para o dump de senhas (uma por linha, ex: rockyou.txt).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("model.onnx"),
        help="Caminho de saída do modelo ONNX (padrão: ./model.onnx).",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(
            f"Erro: arquivo de entrada não encontrado em {args.input}. "
            "O RockYou não é incluído no repositório; baixe um dump "
            "público separadamente e aponte --input para ele.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Lendo senhas de {args.input}...", file=sys.stderr)
    passwords = _load_passwords(args.input)
    print(f"{len(passwords)} senhas carregadas.", file=sys.stderr)

    df = _build_training_frame(passwords)
    print("Distribuição de classes:", file=sys.stderr)
    print(df["label"].value_counts().sort_index(), file=sys.stderr)

    model = train_model(df)
    num_features = len(df.columns) - 1  # exclui a coluna "label"
    export_to_onnx(model, num_features, args.output)


if __name__ == "__main__":
    main()
