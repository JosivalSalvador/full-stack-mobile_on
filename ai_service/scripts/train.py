"""Treina o modelo de classificação de força de senha e exporta para
ONNX.

Roda offline, fora do ciclo de vida do servidor (não é chamado por
nenhuma rota). O artefato gerado (models/password_strength.onnx) é o
que app/engine/ml/registry.py carrega no startup do serviço.

Uso:
    uv run python scripts/train.py --dataset /caminho/para/rockyou.txt

O dataset RockYou não é baixado automaticamente por este script —
precisa estar em disco antes, com um password por linha. As mesmas
features de app/shared/utils.py (extract_password_features) são
usadas aqui no treino e em produção na inferência: se esse cálculo
divergir entre os dois lados, o modelo recebe em produção um vetor de
entrada diferente do que viu durante o treino.

Rótulo de força: não vem do dataset (RockYou não rotula senha por
força). É derivado por heurística determinística a partir das
próprias features (comprimento, diversidade de classe de caractere),
em 3 classes: fraca (0), média (1), forte (2).
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

from app.shared.utils import PasswordFeatures, extract_password_features

_ONNX_OPSET = 18
_N_FEATURES = 7
_TEST_SIZE = 0.2
_RANDOM_STATE = 42


def label_strength(features: PasswordFeatures) -> int:
    """Deriva o rótulo de força (0=fraca, 1=média, 2=forte) a partir
    das features, já que o RockYou não vem rotulado.

    Heurística determinística: conta quantas classes de caractere
    aparecem e o comprimento, sem depender de nenhum modelo já
    treinado (evitaria um ciclo de dependência com o próprio treino).
    """
    char_class_count = sum(
        [
            features.has_upper,
            features.has_lower,
            features.has_digit,
            features.has_special,
        ]
    )

    if features.length < 8 or char_class_count <= 1:
        return 0
    if features.length < 12 or char_class_count <= 2:
        return 1
    return 2


def load_passwords(dataset_path: Path) -> list[str]:
    """Lê o dataset, um password por linha.

    Ignora linhas que não decodificam como UTF-8 (o RockYou original
    tem algumas linhas com encoding inconsistente).
    """
    passwords: list[str] = []
    with dataset_path.open("rb") as file:
        for raw_line in file:
            try:
                password = raw_line.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
            if password:
                passwords.append(password)
    return passwords


def build_training_data(
    passwords: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Extrai features e rótulo de cada senha, monta X (features) e
    y (rótulo) para o treino.
    """
    rows: list[list[float]] = []
    labels: list[int] = []

    for password in passwords:
        features = extract_password_features(password)
        rows.append(features.to_vector())
        labels.append(label_strength(features))

    x = np.array(rows, dtype=np.float32)
    y = np.array(labels, dtype=np.int64)
    return x, y


def train_model(x_train: np.ndarray, y_train: np.ndarray) -> RandomForestClassifier:
    """Treina o classificador de força de senha."""
    classifier = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        random_state=_RANDOM_STATE,
        n_jobs=-1,
    )
    classifier.fit(x_train, y_train)
    return classifier


def export_to_onnx(classifier: RandomForestClassifier, output_path: Path) -> None:
    """Converte o classificador treinado para ONNX e salva em disco."""
    onnx_model = convert_sklearn(
        classifier,
        initial_types=[("input", FloatTensorType([None, _N_FEATURES]))],
        target_opset=_ONNX_OPSET,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(onnx_model.SerializeToString())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Caminho para o arquivo de senhas (uma por linha, ex: rockyou.txt).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/password_strength.onnx"),
        help="Caminho de saída do modelo ONNX.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Limita o número de senhas usadas no treino (útil para teste rápido).",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Erro: dataset não encontrado em {args.dataset}", file=sys.stderr)
        return 1

    print(f"Lendo senhas de {args.dataset}...")
    passwords = load_passwords(args.dataset)
    if args.sample_size:
        passwords = passwords[: args.sample_size]
    print(f"{len(passwords)} senhas carregadas.")

    print("Extraindo features e rótulos...")
    x, y = build_training_data(passwords)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=_TEST_SIZE, random_state=_RANDOM_STATE, stratify=y
    )

    print(f"Treinando com {len(x_train)} amostras...")
    classifier = train_model(x_train, y_train)

    accuracy = classifier.score(x_test, y_test)
    print(f"Acurácia no conjunto de teste ({len(x_test)} amostras): {accuracy:.4f}")

    label_counts = pd.Series(y).value_counts().sort_index()
    print(f"Distribuição de rótulos: {label_counts.to_dict()}")

    print(f"Exportando para ONNX em {args.output}...")
    export_to_onnx(classifier, args.output)
    print("Concluído.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
