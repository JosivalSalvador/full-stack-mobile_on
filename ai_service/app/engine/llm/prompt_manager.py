"""Montagem dos prompts enviados ao Ollama para gerar a explicação de força.

Separado de app/engine/llm/client.py de propósito: este módulo só
decide o *conteúdo* do prompt (o quê perguntar), client.py decide
*como* a chamada é feita (retry, timeout, autenticação). Isso permite
testar o texto do prompt sem precisar mockar rede.

Nunca inclui a senha em si no prompt — só o resultado já classificado
(label, probabilidades, features não sensíveis como comprimento e
classes de caractere). O Ollama Cloud é um provider externo; a senha
do usuário não deve deixar o processo do ai_service.
"""

from app.engine.ml.batcher import PredictionResult
from app.shared.utils import PasswordFeatures

_STRENGTH_LABELS = {0: "fraca", 1: "média", 2: "forte"}

_SYSTEM_PROMPT = (
    "Você é um assistente de segurança que explica, em português "
    "do Brasil, por que uma senha recebeu uma classificação de força "
    "específica. Você nunca vê a senha real, apenas características "
    "dela e o resultado de um classificador de machine learning. "
    "Responda em no máximo 2 frases, direto ao ponto, sem saudação "
    "nem despedida. Se a senha for fraca ou média, inclua uma "
    "sugestão concreta de melhoria; se for forte, apenas confirme "
    "o motivo."
)


def _describe_features(features: PasswordFeatures) -> str:
    """Traduz PasswordFeatures para uma descrição textual em pt-BR,
    o que o LLM recebe em vez dos valores brutos de features.
    """
    parts = [f"{features.length} caracteres"]

    char_classes = []
    if features.has_upper:
        char_classes.append("maiúsculas")
    if features.has_lower:
        char_classes.append("minúsculas")
    if features.has_digit:
        char_classes.append("números")
    if features.has_special:
        char_classes.append("símbolos")

    if char_classes:
        parts.append("contém " + ", ".join(char_classes))
    else:
        parts.append("não contém variação de tipo de caractere")

    if features.has_keyboard_sequence:
        parts.append("contém uma sequência de teclado comum (ex: qwerty)")

    return "; ".join(parts)


def build_explanation_messages(
    features: PasswordFeatures, prediction: PredictionResult
) -> list[dict[str, str]]:
    """Monta a lista de mensagens no formato esperado por
    ollama.AsyncClient.chat(messages=...).

    Chamado por app/modules/vault_audit/pipeline.py, uma vez por
    senha analisada, depois que app/engine/ml/batcher.py já retornou
    o PredictionResult. app/engine/llm/client.py recebe o resultado
    desta função e repassa direto para a chamada HTTP.
    """
    strength_label = _STRENGTH_LABELS[prediction.label]
    confidence = prediction.probabilities[prediction.label]
    feature_description = _describe_features(features)

    user_prompt = (
        f"Uma senha foi classificada como '{strength_label}' "
        f"(confiança do modelo: {confidence:.0%}). "
        f"Características da senha: {feature_description}. "
        "Explique o motivo desta classificação e, se aplicável, "
        "sugira como torná-la mais forte."
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
