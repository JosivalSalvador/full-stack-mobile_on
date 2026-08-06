"""Carregamento do modelo ONNX de força de senha a partir do disco.

Responsável apenas por ler o arquivo .onnx e construir uma
InferenceSession do ONNX Runtime. app/engine/ml/registry.py é quem
guarda essa sessão em memória durante o ciclo de vida do serviço e a
expõe para app/modules/vault_audit/pipeline.py.
"""

import hashlib
from pathlib import Path

import onnxruntime as ort

from app.core.config import settings
from app.core.logging import get_logger
from app.shared.exceptions import ModelNotReadyError

logger = get_logger(__name__)


def _compute_file_hash(path: Path) -> str:
    """Calcula o SHA-256 do arquivo do modelo, para fins de log e
    rastreabilidade (qual versão exata do modelo está rodando).

    Não compara contra um hash esperado: essa validação exigiria um
    valor de referência configurado em algum lugar (ex.: uma variável
    nova em .env.example), decisão que ainda não foi tomada. Por ora,
    o hash calculado aqui aparece no log de startup do serviço,
    permitindo conferência manual quando necessário.
    """
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_model(model_path: Path | None = None) -> ort.InferenceSession:
    """Carrega o modelo ONNX do disco e retorna uma InferenceSession pronta.

    Chamado por app/engine/ml/registry.py no startup do serviço (via
    lifespan de app/main.py) e por
    workers/tasks/model_tasks.py quando um modelo retreinado precisa
    ser recarregado sem reiniciar o processo.

    Levanta ModelNotReadyError se o arquivo não existir ou se o ONNX
    Runtime falhar ao construir a sessão (arquivo corrompido, formato
    inválido) — o chamador decide se isso derruba o startup do
    serviço ou se mantém o modelo anterior em caso de reload.
    """
    path = model_path if model_path is not None else Path(settings.model_path)

    if not path.exists():
        raise ModelNotReadyError(
            f"Arquivo de modelo não encontrado em {path}. "
            "Rode scripts/train.py para gerar o .onnx, ou verifique "
            "MODEL_PATH em .env."
        )

    file_hash = _compute_file_hash(path)
    logger.info("model_load_started", path=str(path), sha256=file_hash)

    try:
        session = ort.InferenceSession(
            str(path),
            providers=["CPUExecutionProvider"],
        )
    except Exception as exc:
        raise ModelNotReadyError(
            f"Falha ao carregar modelo ONNX de {path}: {exc}"
        ) from exc

    input_meta = session.get_inputs()[0]
    logger.info(
        "model_load_finished",
        path=str(path),
        sha256=file_hash,
        input_name=input_meta.name,
        input_shape=input_meta.shape,
    )

    return session
