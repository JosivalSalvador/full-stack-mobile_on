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

    # --- Provider de LLM externo (Ollama Cloud, tier gratuito) ---
    ollama_host: str = Field(
        default="https://ollama.com",
        description=(
            "URL base do Ollama. Aponta para o Ollama Cloud por padrão "
            "(tier Free, sem custo); pode apontar para uma instância "
            "local (ex: http://localhost:11434) em desenvolvimento."
        ),
    )
    ollama_api_key: str = Field(
        default="",
        description=(
            "Chave da API do Ollama Cloud, usada pelo provider "
            "external_llm. Vazia quando ollama_host aponta para uma "
            "instância local, que não exige autenticação."
        ),
    )
    ollama_model: str = Field(
        default="gpt-oss:20b",
        description="Modelo nível 1 (leve), dentro da cota do tier Free.",
    )

    # --- Segurança da própria API ---
    # Defesa em profundidade: este serviço só deveria ser alcançado
    # pelo backend Go, dentro da rede interna do Docker, nunca exposto
    # diretamente à internet. A API key confirma que quem chama é o
    # backend de fato, não substitui autenticação do usuário final
    # (essa é responsabilidade do backend Go).
    api_key: str = Field(
        description=(
            "Chave secreta compartilhada com o backend Go, enviada no "
            "header X-API-Key em toda chamada."
        ),
    )
    rate_limit_requests: int = Field(
        default=100,
        description="Máximo de requisições aceitas por identificador na janela.",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        description="Duração da janela de contagem do rate limit, em segundos.",
    )

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

