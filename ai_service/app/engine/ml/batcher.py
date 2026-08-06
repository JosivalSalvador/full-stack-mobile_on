"""Agrupamento de chamadas de inferência ONNX em lotes.

session.run() do ONNX Runtime tem overhead fixo por chamada; agrupar N
pedidos concorrentes de "qual a força desta senha" em uma única
chamada com um batch de N linhas reduz esse overhead por item. Este
módulo implementa uma janela de coleta: pedidos que chegam dentro de
_BATCH_WINDOW_SECONDS (ou até _MAX_BATCH_SIZE ser atingido antes)
disparam juntos.

app/modules/vault_audit/pipeline.py chama predict_one() por senha
individual; internamente, cada chamada entra na fila de um lote em
formação e recebe seu resultado quando o lote é despachado.
"""

import asyncio
from dataclasses import dataclass, field

import numpy as np

from app.core.logging import get_logger
from app.engine.ml.registry import ModelRegistry
from app.shared.utils import PasswordFeatures

logger = get_logger(__name__)

_MAX_BATCH_SIZE = 32
_BATCH_WINDOW_SECONDS = 0.01

# Nomes de output confirmados empiricamente: um RandomForestClassifier
# convertido via skl2onnx (convert_sklearn) expõe exatamente estes dois
# nomes, não "label"/"probabilities" como se poderia supor. Alterar o
# processo de treino em scripts/train.py pode mudar esses nomes; se
# scripts/train.py mudar de biblioteca de classificador, revalidar.
_OUTPUT_LABEL_NAME = "output_label"
_OUTPUT_PROBABILITY_NAME = "output_probability"


@dataclass
class PredictionResult:
    """Resultado de uma inferência sobre uma única senha.

    label é a classe prevista (0=fraca, 1=média, 2=forte, mesma
    codificação usada por scripts/train.py). probabilities mapeia
    cada classe à sua probabilidade, na forma como o ONNX Runtime as
    devolve para um RandomForestClassifier (um dict por item de
    batch, não um tensor denso).
    """

    label: int
    probabilities: dict[int, float]


@dataclass
class _PendingRequest:
    """Um pedido de inferência ainda não despachado, aguardando o
    lote fechar.
    """

    features: PasswordFeatures
    future: asyncio.Future[PredictionResult] = field(
        default_factory=asyncio.Future
    )


class InferenceBatcher:
    """Coleta pedidos de inferência e os despacha em lotes ao ModelRegistry.

    Uma instância vive presa ao app.state do FastAPI, criada junto do
    ModelRegistry no lifespan de app/main.py. Não é thread-safe por
    threading.Lock (como ModelRegistry): usa apenas primitivas de
    asyncio, corretas para o event loop único do FastAPI/Uvicorn.
    """

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry
        self._pending: list[_PendingRequest] = []
        self._flush_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def predict_one(self, features: PasswordFeatures) -> PredictionResult:
        """Enfileira uma senha para inferência e aguarda o resultado do lote.

        Chamado por app/modules/vault_audit/pipeline.py, uma vez por
        senha. Do ponto de vista de quem chama, é uma chamada
        assíncrona comum; o agrupamento em lote acontece de forma
        transparente.
        """
        request = _PendingRequest(features=features)

        async with self._lock:
            self._pending.append(request)

            if len(self._pending) >= _MAX_BATCH_SIZE:
                await self._flush_locked()
            elif self._flush_task is None:
                self._flush_task = asyncio.create_task(self._schedule_flush())

        return await request.future

    async def _schedule_flush(self) -> None:
        """Aguarda a janela de coleta e despacha o lote formado até então.

        Cancelado implicitamente se _flush_locked() já rodou por
        atingir _MAX_BATCH_SIZE antes do timeout: neste caso
        self._flush_task é resetado antes deste sleep terminar, e o
        despacho por tamanho já terá esvaziado self._pending.
        """
        await asyncio.sleep(_BATCH_WINDOW_SECONDS)

        async with self._lock:
            if self._pending:
                await self._flush_locked()

    async def _flush_locked(self) -> None:
        """Despacha o lote atual ao ModelRegistry e resolve os futures.

        Deve ser chamado apenas com self._lock já adquirido pelo
        chamador (predict_one ou _schedule_flush), daí o sufixo
        _locked no nome.
        """
        batch = self._pending
        self._pending = []
        self._flush_task = None

        try:
            results = self._run_inference(batch)
            for request, result in zip(batch, results, strict=True):
                if not request.future.done():
                    request.future.set_result(result)
        except Exception as exc:
            logger.error(
                "batch_inference_failed", batch_size=len(batch), error=str(exc)
            )
            for request in batch:
                if not request.future.done():
                    request.future.set_exception(exc)

    def _run_inference(
        self, batch: list[_PendingRequest]
    ) -> list[PredictionResult]:
        """Monta o array numpy do lote e chama session.run() uma única vez.

        Roda de forma síncrona (onnxruntime não é async nativamente);
        como cada chamada é rápida (modelo pequeno, CPU), isso não
        bloqueia o event loop de forma perceptível na janela de
        _BATCH_WINDOW_SECONDS configurada. Se o modelo crescer a
        ponto disso importar, mover para asyncio.to_thread() é o
        próximo passo.
        """
        session = self._registry.get_session()

        input_array = np.array(
            [request.features.to_vector() for request in batch],
            dtype=np.float32,
        )

        outputs = session.run(
            [_OUTPUT_LABEL_NAME, _OUTPUT_PROBABILITY_NAME],
            {"input": input_array},
        )
        labels, probabilities_list = outputs

        return [
            PredictionResult(label=int(label), probabilities=dict(probs))
            for label, probs in zip(labels, probabilities_list, strict=True)
        ]
