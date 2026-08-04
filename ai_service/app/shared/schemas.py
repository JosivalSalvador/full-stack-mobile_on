"""Schemas reutilizáveis, compartilhados por todos os módulos da API.

Contratos genéricos (envelope de resposta, paginação, consumo de
tokens) que não pertencem a nenhum módulo de domínio específico e
evitam duplicação entre app/modules/*.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Contador de tokens consumidos em uma chamada de LLM."""

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ResponseMeta(BaseModel):
    """Metadados anexados a toda resposta da API.

    correlation_id é propagado pelo app/api/middleware.py; token_usage
    só é preenchido em respostas que envolveram uma chamada de LLM.
    """

    correlation_id: str
    token_usage: TokenUsage | None = None


class Envelope[DataT](BaseModel):
    """Envelope padrão de resposta: dados de negócio separados de meta."""

    data: DataT
    meta: ResponseMeta


class PaginationParams(BaseModel):
    """Parâmetros de paginação aceitos em endpoints de listagem."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedEnvelope[DataT](BaseModel):
    """Envelope de resposta paginada."""

    data: list[DataT]
    meta: ResponseMeta
    page: int
    page_size: int
    total_items: int
