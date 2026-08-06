"""Configuração central do ai_service, lida de variáveis de ambiente.

Único ponto de leitura de .env em todo o serviço — nenhum outro módulo
deve chamar os.environ diretamente. Todo o resto do serviço importa a
instância `settings` já validada, em vez de reler variáveis soltas.

O conjunto de campos aqui espelha exatamente o que está documentado em
.env.example: qualquer variável nova precisa ser adicionada nos dois
lugares, para não ficar um `.env` real fora de sincronia com o exemplo
que orienta quem for configurar o serviço.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração validada do ai_service.

    Os nomes dos campos usam exatamente as chaves do .env (case
    insensitive por padrão do pydantic-settings), então não há
    necessidade de aliasing manual.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignora variáveis de ambiente extras não mapeadas aqui, em vez
        # de falhar — o ambiente de execução (Docker, CI) pode ter
        # outras variáveis do sistema que não dizem respeito ao
        # ai_service.
        extra="ignore",
    )

    # --- Aplicação ---
    environment: str = "development"
    log_level: str = "INFO"

    # --- Banco de dados ---
    # URL completa de conexão asyncpg, incluindo usuário e senha do
    # banco ai_service_db (ver infra/postgres/init.sql).
    database_url: str

    # --- Provider de LLM externo (Ollama Cloud) ---
    ollama_host: str = "https://ollama.com"
    # Vazia por padrão: o tier Free do Ollama Cloud aceita chamada sem
    # chave, e uma instância local (OLLAMA_HOST=http://localhost:11434)
    # também não exige. Só é obrigatória se o provider externo exigir.
    ollama_api_key: str = ""
    ollama_model: str = "gpt-oss:20b"

    # --- Segurança interna (backend Go -> ai_service) ---
    # Vazia por padrão para não travar setup local antes do valor real
    # ser gerado; app/core/security.py trata string vazia como "auth
    # desabilitada" apenas em ambiente de development, nunca em
    # production (ver security.py, fase 2).
    internal_api_key: str = ""

    # --- Rate limiting (em memória, sem Redis) ---
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 60

    @property
    def is_production(self) -> bool:
        """Atalho usado por security.py e main.py para decisões que
        diferem entre desenvolvimento e produção (ex.: exigir
        INTERNAL_API_KEY não vazia).
        """
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância de Settings, construída uma única vez.

    Usar uma função cacheada (em vez de instanciar Settings() direto
    no nível do módulo) permite que app/api/dependencies.py e os
    testes substituam a configuração via override do FastAPI
    (app.dependency_overrides[get_settings]) sem precisar mexer em
    variável de ambiente de verdade.
    """
    return Settings()


settings = get_settings()
