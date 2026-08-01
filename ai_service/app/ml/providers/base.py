"""Contrato comum dos providers de IA.

Um provider é qualquer "motor" capaz de processar uma entrada e
devolver uma saída — seja um modelo próprio rodando localmente, seja
uma chamada a um LLM externo. Quem consome um provider (pipelines,
services) depende apenas deste contrato, nunca da implementação
concreta por trás dele.

Isso é o que permite trocar de provider, ou compor vários no mesmo
fluxo, sem que o código que os usa precise saber a diferença.
"""

from abc import ABC, abstractmethod


class Provider[InputT, OutputT](ABC):
    """Interface que todo provider de IA deve implementar.

    `InputT` e `OutputT` são os tipos de entrada e saída específicos
    de cada provider concreto (ex: `local_model.py` recebe uma senha
    e devolve uma avaliação de força; `external_llm.py` recebe um
    prompt e devolve texto).
    """

    @abstractmethod
    async def run(self, data: InputT) -> OutputT:
        """Processa `data` e devolve o resultado.

        Implementações locais (que não fazem I/O de rede) ainda devem
        ser `async def` para manter o contrato uniforme — mesmo que o
        corpo seja síncrono por dentro, ela roda em uma corrotina que
        não bloqueia o event loop de quem chama.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome curto do provider, usado em logs e métricas."""
        ...
