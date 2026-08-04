"""Contrato para provedores de LLM externo, chamados via rede.

Diferente de um modelo local (`ml_model.py`), um provedor de LLM
faz uma chamada de rede a um serviço fora do nosso controle. O
contrato de entrada de qualquer uso deste tipo de provedor deve ser
desenhado para nunca receber dado sensível em texto puro — apenas
metadados já processados/anonimizados. Implementações concretas
ficam em `infrastructure/llm_providers/`.
"""

from abc import ABC, abstractmethod


class LLMProviderError(Exception):
    """Erro ao chamar um provedor de LLM externo."""


class LLMProvider[InputT, OutputT](ABC):
    """Interface que todo provedor de LLM externo deve implementar."""

    @abstractmethod
    async def generate(self, data: InputT) -> OutputT:
        """Processa `data` via chamada de rede e devolve o resultado.

        Implementações devem capturar erro de rede ou de resposta
        inesperada e relançar como `LLMProviderError`, para que quem
        chama decida como lidar com a falha sem precisar conhecer os
        detalhes do provedor específico por trás.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome curto do provedor, usado em logs e métricas."""
        ...
