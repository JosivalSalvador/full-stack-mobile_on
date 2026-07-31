"""Configuração central do ai_service.

Toda variável de ambiente que o serviço precisa é declarada e validada
aqui, uma única vez. Nenhum outro módulo deve ler `os.environ` direto:
sempre importam `settings` a partir daqui.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variáveis de ambiente do ai_service, validadas na inicialização."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Aplicação ---
    app_name: str = "ai_service"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # --- Banco de dados ---
    # "Database per service": este serviço tem credencial e schema
    # próprios, nunca lê tabela de outro serviço diretamente.
    database_url: str = Field(
        description=(
            "URL de conexão async com o Postgres, ex: "
            "postgresql+asyncpg://user:pass@host:5432/ai_service_db"
        ),
    )

    # --- Provider de LLM externo ---
    anthropic_api_key: str = Field(
        default="",
        description=(
            "Chave da API da Anthropic, usada pelo provider "
            "external_llm. Vazia em ambientes onde o LLM não é "
            "chamado (ex: alguns testes)."
        ),
    )
    anthropic_model: str = Field(default="claude-haiku-4-5-20251001")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única (cacheada) de Settings.

    Usar `lru_cache` garante que o .env só é lido e validado uma vez
    por processo, e que todo módulo que pedir `get_settings()` recebe
    o mesmo objeto.
    """
    return Settings()
