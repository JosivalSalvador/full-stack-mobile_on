"""Contrato para modelos de IA que rodam localmente, no próprio processo.

Um modelo local processa dado sem sair da máquina, sem I/O de rede.
Isso permite avaliar informação sensível (como uma senha) sem que ela
nunca deixe o processo. Implementações concretas ficam em
`infrastructure/ml_models/`.
"""

from abc import ABC, abstractmethod


class MLModel[InputT, OutputT](ABC):
    """Interface que todo modelo local de IA deve implementar."""

    @abstractmethod
    async def predict(self, data: InputT) -> OutputT:
        """Processa `data` e devolve o resultado.

        Mesmo sendo síncrono por dentro (sem I/O de rede), o método é
        `async def` para manter o contrato uniforme com o restante do
        sistema, que é assíncrono por natureza.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome curto do modelo, usado em logs e métricas."""
        ...
