"""Prompts usados para instruir o LLM externo na explicação da
auditoria de vault.

Fica isolado em domain/ (não em infrastructure/) porque o texto do
prompt é regra de negócio — o que dizer ao LLM e como — não detalhe
de implementação de um provedor específico. Trocar de provedor de LLM
não deveria exigir reescrever o prompt.
"""

AUDIT_EXPLANATION_SYSTEM_PROMPT = (
    "Você explica avaliações de força de senha de forma breve e "
    "clara, em português, para uma pessoa leiga. Nunca peça, "
    "sugira ou mencione a senha em si — você só recebe metadados "
    "já anonimizados. Responda em no máximo 2 frases."
)


def build_audit_explanation_prompt(
    score: int,
    warning: str,
    suggestions: tuple[str, ...],
    crack_time_display: str,
) -> str:
    """Monta o prompt de usuário a partir dos metadados já anonimizados
    de uma avaliação de força de senha.

    Nunca recebe a senha em si como parâmetro — só os campos já
    derivados pelo modelo local.
    """
    return (
        f"Score de força: {score}/4. "
        f"Aviso técnico: {warning or 'nenhum'}. "
        f"Sugestões técnicas: {'; '.join(suggestions) or 'nenhuma'}. "
        f"Tempo estimado de quebra offline: {crack_time_display}."
    )
