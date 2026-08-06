"""Registro em memória do modelo ONNX carregado, com suporte a reload.

Guarda a InferenceSession construída por app/engine/ml/loader.py
durante todo o ciclo de vida do serviço, e a expõe para
app/modules/vault_audit/pipeline.py via get_session(). Diferente de
loader.py (que só sabe ler o arquivo do disco), este módulo é quem
tem estado: uma instância de ModelRegistry vive presa ao app.state do
FastAPI, criada no lifespan de app/main.py.
"""

import threading
from pathlib import Path

import onnxruntime as ort

from app.core.logging import get_logger
from app.engine.ml.loader import load_model
from app.shared.exceptions import ModelNotReadyError

logger = get_logger(__name__)


class ModelRegistry:
    """Guarda a InferenceSession ativa e permite trocá-la em runtime.

    O lock protege a troca de sessão contra corrida entre uma
    requisição em andamento (lendo self._session) e um reload
    disparado por workers/tasks/model_tasks.py quando um novo .onnx
    termina de ser treinado. Sem o lock, uma requisição poderia pegar
    a sessão antiga no meio de uma troca e falhar de forma
    imprevisível.
    """

    def __init__(self) -> None:
        self._session: ort.InferenceSession | None = None
        self._lock = threading.Lock()

    def load(self, model_path: Path | None = None) -> None:
        """Carrega (ou recarrega) o modelo e substitui a sessão ativa.

        Chamado no startup do serviço (lifespan de app/main.py) e por
        workers/tasks/model_tasks.py após um retreino. Se load_model()
        levantar ModelNotReadyError, a sessão anterior (se existir) é
        mantida — um reload que falha não deve derrubar um modelo que
        já estava funcionando.
        """
        new_session = load_model(model_path)

        with self._lock:
            self._session = new_session

        logger.info("model_registry_updated")

    def get_session(self) -> ort.InferenceSession:
        """Retorna a sessão ativa, para app/engine/ml/batcher.py chamar
        session.run() sobre ela.

        Levanta ModelNotReadyError se load() ainda não foi chamado —
        situação que app/api/v1/endpoints/health.py usa para reportar
        o serviço como não pronto antes do startup terminar.
        """
        with self._lock:
            if self._session is None:
                raise ModelNotReadyError(
                    "Nenhum modelo carregado ainda. "
                    "ModelRegistry.load() precisa ser chamado antes de "
                    "qualquer inferência."
                )
            return self._session

    def is_ready(self) -> bool:
        """Verificação sem exceção, usada por health.py para reportar
        status sem precisar tratar ModelNotReadyError como fluxo
        normal de controle.
        """
        with self._lock:
            return self._session is not None


# Instância única do processo. app/main.py chama model_registry.load()
# no lifespan; app/api/dependencies.py expõe essa mesma instância via
# Depends() para as rotas que precisam de inferência.
model_registry = ModelRegistry()
