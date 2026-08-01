"""Pipeline de auditoria de vault: orquestra os dois providers de IA.

Fluxo, em ordem fixa e deliberada:
    1. Provider LOCAL (zxcvbn) analisa cada senha do vault. Roda
       sempre primeiro porque é ele quem processa a senha em si — o
       resultado não depende de rede nem de terceiros.
    2. Provider EXTERNO (Ollama) recebe só os metadados já anonimizados
       do resultado local e gera uma explicação em texto.

O pipeline não processa conteúdo por conta própria — ele só decide a
ordem e como combinar o que cada provider devolve. Essa separação é o
que permite trocar de provider (ex: outro modelo local, outro LLM) sem
tocar neste arquivo.

Resiliência: se o provider externo falhar, a auditoria não é
descartada. O score do provider local, que é o dado que importa de
fato, continua válido; a explicação em texto fica ausente nesse item.
"""

from dataclasses import dataclass

from app.core.logging import get_logger
from app.ml.providers.external_llm import (
    ExternalLLMProvider as ExternalLLMType,
    LLMExplanationRequest,
    LLMProviderError,
)
from app.ml.providers.local_model import (
    LocalPasswordModel as LocalModelType,
    PasswordStrengthResult,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class VaultItemAudit:
    """Resultado da auditoria de um único item do vault."""

    item_id: str
    strength: PasswordStrengthResult
    explanation: str | None
    """None quando o provider externo falhou; o score local ainda é
    válido mesmo assim."""


async def audit_vault_item(
    item_id: str,
    password: str,
    *,
    local_model: LocalModelType,
    external_llm: ExternalLLMType,
) -> VaultItemAudit:
    """Audita uma única senha do vault, combinando os dois providers.

    `password` nunca é passado ao provider externo — só os campos
    derivados do resultado local (que já não contém a senha) seguem
    adiante.
    """
    strength = await local_model.run(password)

    explanation_request = LLMExplanationRequest(
        score=strength.score,
        warning=strength.warning,
        suggestions=strength.suggestions,
        crack_time_display=strength.crack_time_display,
    )

    try:
        explanation = await external_llm.run(explanation_request)
    except LLMProviderError:
        logger.warning(
            "vault_audit_explanation_unavailable",
            item_id=item_id,
            reason="external_llm_failed",
        )
        explanation = None

    return VaultItemAudit(
        item_id=item_id,
        strength=strength,
        explanation=explanation,
    )


async def audit_vault(
    items: dict[str, str],
    *,
    local_model: LocalModelType,
    external_llm: ExternalLLMType,
) -> list[VaultItemAudit]:
    """Audita todas as senhas de `items` (item_id -> senha).

    Cada item é processado de forma independente: a falha do provider
    externo em um item não afeta os demais.
    """
    return [
        await audit_vault_item(
            item_id,
            password,
            local_model=local_model,
            external_llm=external_llm,
        )
        for item_id, password in items.items()
    ]
