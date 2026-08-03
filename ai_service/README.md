# ai_service

Base/template de serviço de IA em FastAPI + Python, parte do monorepo `keymory_on`. Este documento explica o que cada pasta faz e como usar a implementação de exemplo (`vault_audit`) como molde para criar um domínio novo.

## Como ler este documento

O serviço tem um único domínio implementado hoje, `vault_audit`, que audita a força de senhas de um vault. Ele não é o produto final, é o exemplo vivo da estrutura, do mesmo jeito que uma peça de amostra ensina a montar um móvel novo. Toda vez que este documento mostra um trecho de `vault_audit`, é para ilustrar o padrão, não para descrever uma funcionalidade que precisa continuar existindo.

## Stack

FastAPI e Uvicorn sobem o servidor HTTP assíncrono. SQLModel, SQLAlchemy assíncrono e asyncpg cuidam do acesso ao Postgres. Alembic versiona as mudanças de schema do banco. structlog produz log estruturado, em JSON quando `ENVIRONMENT=production`, em texto legível no terminal em desenvolvimento. zxcvbn é o provider local de análise de senha, roda na memória do processo, nunca manda a senha para fora. Ollama Cloud é o provider externo de LLM, com tier gratuito permanente. pytest, pytest-cov e respx cuidam de testes, cobertura e mock de chamada HTTP. ruff faz lint e formatação. mypy, em modo `strict`, faz a checagem de tipo.

## Estrutura de pastas: o que é cada uma

```
ai_service/
├── alembic/
├── app/
│   ├── core/
│   ├── modules/
│   │   └── vault_audit/        (exemplo)
│   ├── ml/
│   │   ├── providers/
│   │   └── pipelines/
│   ├── repositories/
│   ├── workers/
│   ├── api.py
│   └── main.py
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile
├── docker-compose.yml (na raiz do monorepo, não aqui)
└── pyproject.toml
```

### `alembic/`

Guarda o histórico de mudanças no schema do banco. `env.py` conecta no Postgres usando a mesma `DATABASE_URL` que o resto do serviço lê de `core/config.py`, não uma configuração separada. `versions/` recebe um arquivo por migration, sempre gerado pelo comando `alembic revision --autogenerate`, nunca escrito à mão. `script.py.mako` é o modelo que o Alembic usa para montar cada arquivo novo dessa pasta.

A única migration existente hoje é o exemplo de `vault_audit`: cria a tabela `vault_item_audits`, com as colunas `id`, `user_id`, `item_id`, `score`, `is_weak`, `warning`, `crack_time_display`, `explanation` e `audited_at`, mais três índices, em `user_id`, `item_id` e `audited_at`, para acelerar as buscas que o repository desse domínio faz por usuário e por data. Toda migration gerada pelo Alembic vem com duas funções, `upgrade()`, que aplica a mudança, e `downgrade()`, que desfaz, na ordem inversa da criação (primeiro os índices, depois a tabela). O nome do arquivo, algo como `2026_08_02_1449-71e7d978e434_create_vault_item_audits_table`, junta data, hora, um hash de revisão e um resumo da mudança, o que ajuda a ordenar migrations visualmente dentro da pasta.

### `app/core/`

Infraestrutura compartilhada por todo o serviço, o único lugar que qualquer módulo de domínio pode importar sem quebrar a separação de camadas.

`config.py` lê e valida as variáveis de ambiente uma única vez, no início do processo. Qualquer módulo que precise de uma configuração importa `get_settings()` daqui, nunca lê `os.environ` direto.

`database.py` cria o engine assíncrono e expõe duas formas de pegar uma sessão de banco: `get_db_session()` para ser usado como dependency do FastAPI dentro de uma rota, e `db_session_context()` para ser usado fora do ciclo de uma requisição HTTP, como dentro de um worker.

`logging.py` configura o structlog. Chama `configure_logging()` uma vez, em `main.py`, antes de qualquer outro código rodar.

### `app/modules/`

Cada domínio de negócio do serviço mora aqui, uma pasta por domínio. Hoje só existe `vault_audit/`, que serve de molde. Dentro de cada domínio:

`router.py` é a borda HTTP, define as rotas, recebe a requisição já validada pelo schema, chama o service, devolve a resposta.

`service.py` é a regra de negócio. Não importa FastAPI nem SQLAlchemy, só conhece a interface do repository e as funções do pipeline de IA. Isso é o que permite testar a regra de negócio sem precisar de servidor nem de banco real.

`schemas.py` define o formato de entrada e saída da API, usando Pydantic. É diferente do modelo de banco.

`models.py` define a tabela SQLModel, o formato de como o dado fica salvo.

`repositories/repository.py` é a interface, o que é possível fazer com o dado, sem dizer como. `repositories/repository_impl.py` é a implementação real, a única camada do domínio que fala com SQLAlchemy diretamente.

No exemplo `vault_audit`, essa estrutura foi preenchida assim: `router.py` expõe `POST /vault-audit`, `service.py` recebe a lista de senhas, chama o pipeline de IA para cada uma e manda salvar o resultado, `schemas.py` define o contrato de entrada (lista de senhas por item) e saída (nota, aviso, explicação), `models.py` define a tabela `vault_item_audits`, e o repository salva e busca esses registros.

### `app/ml/`

Tudo relacionado a inteligência artificial do serviço, separado dos domínios de negócio porque a forma de trabalhar com modelo de IA é diferente da forma de trabalhar com CRUD comum.

`providers/base.py` define o contrato comum que qualquer provider de IA precisa seguir, um método `run()` que recebe uma entrada e devolve uma saída. Isso é o que permite trocar de provider, ou usar mais de um no mesmo fluxo, sem que o resto do código precise saber a diferença.

`providers/` guarda as implementações concretas desse contrato. No exemplo, existem duas: um provider local, que roda um algoritmo (zxcvbn) direto na memória do processo, sem sair para a rede, e um provider externo, que manda uma chamada HTTP para um LLM (Ollama Cloud) e devolve o texto de resposta.

`pipelines/` guarda a orquestração, o código que decide em que ordem os providers são chamados e como o resultado de cada um se combina. A peça de pipeline não processa dado sozinha, só decide o fluxo.

`model_loader.py` garante que cada provider é criado uma única vez, quando o serviço sobe, e reaproveitado em toda chamada seguinte, em vez de criar uma instância nova a cada requisição.

`train.py` é o lugar reservado para atualizar o conhecimento do provider local. Para um algoritmo como o zxcvbn, isso não é treino de rede neural, é atualizar a lista de padrões que ele reconhece.

No exemplo, o provider local roda zxcvbn sobre a senha e nunca deixa a senha sair do processo. O resultado dessa análise (uma nota, um aviso, um tempo estimado de quebra, nunca a senha) é o que vai para o provider externo, que pede ao LLM uma explicação em texto. O pipeline chama sempre o provider local primeiro, depois o externo, e se o externo falhar a resposta continua válida, só sem o texto explicativo.

### `app/repositories/`

Acesso a dado que não pertence a um domínio específico, reaproveitável por qualquer módulo. No exemplo, guarda uma função de verificação de saúde do banco, usada tanto pela rota `/health` quanto por um worker que precisa confirmar que o banco está de pé antes de começar um trabalho pesado.

### `app/workers/`

Tarefas que rodam fora do caminho de resposta de uma requisição HTTP, usando o `BackgroundTasks` do próprio FastAPI. No exemplo, existe uma tarefa que atualiza a lista de senhas vazadas conhecidas e reaudita um vault inteiro em segundo plano.

### `app/api.py` e `app/main.py`

`api.py` é o ponto único que junta o router de cada módulo. Criar um domínio novo significa registrar o router dele aqui, e só aqui. `main.py` é o ponto de entrada, sobe o app FastAPI, configura o log, carrega os providers de IA uma vez no início, e expõe a rota `/health`.

### `tests/`

`tests/unit/` espelha a árvore de `app/`, pasta por pasta. Cada teste unitário usa fakes no lugar dos providers de IA reais, nenhum bate em rede de verdade. `tests/integration/` sobe o app inteiro em memória e testa o fluxo completo, mockando só o transporte HTTP externo, o resto (rota, regra de negócio, pipeline, banco) roda de verdade. Os dois usam um Postgres separado do de desenvolvimento, para nunca sujar dado real ao rodar os testes.

Duas fixtures compartilhadas sustentam isso. `tests/conftest.py`, na raiz da pasta, fica ali porque um `conftest.py` só alcança quem está abaixo dele na árvore, então precisa estar nesse nível para valer tanto para `unit/` quanto para `integration/`. Ele define `test_db_session`, que abre uma sessão contra o Postgres de teste (porta separada da de desenvolvimento), cria o schema do zero antes de cada teste que usar essa fixture, e derruba o schema depois, garantindo que um teste nunca herda dado deixado por outro. `tests/unit/conftest.py`, dentro de `unit/`, é onde moram os fakes usados só pelos testes unitários. No exemplo do `vault_audit`, `FakeLocalModel` e `FakeExternalLLM` implementam o mesmo contrato de `Provider` das versões reais, mas devolvem resultado fixo e determinístico, sem rodar zxcvbn nem chamar um LLM de verdade. Um domínio novo que também use IA reaproveita ou estende esses fakes, em vez de recriar o padrão do zero.

## Duas regras que sustentam a estrutura

`core/` nunca importa nada de dentro de `modules/`. Infraestrutura não conhece domínio de negócio.

`service.py` e tudo dentro de `ml/` nunca importam FastAPI. Regra de negócio e lógica de IA precisam ser testáveis sem precisar de um servidor rodando.

## Arquivos de configuração

Além do código em `app/`, alguns arquivos na raiz do serviço configuram como ele é construído, testado e mantido consistente.

### `pyproject.toml`

Arquivo central de configuração do projeto Python. Além de listar as dependências de produção (`fastapi`, `sqlmodel`, `alembic`, `structlog`, `zxcvbn`, `ollama`, entre outras) separadas das dependências de desenvolvimento (`pytest` e seus plugins, `ruff`, `mypy`, `httpx`, `respx`), ele configura três ferramentas:

O `ruff`, usado tanto como linter quanto como formatador. `line-length = 88` fixa o limite de coluna. As regras ligadas em `select` cobrem sintaxe e estilo PEP 8, imports não usados, ordenação de imports, prevenção de bugs comuns, sintaxe atualizada para Python 3.12 ou mais recente, nomenclatura PEP 8, boas práticas específicas de FastAPI, e regras próprias do Ruff. Uma única regra é desligada em `ignore`, a `B008`, que por padrão reclamaria do uso de `Depends(...)` como valor default de parâmetro, um padrão normal em rotas FastAPI. A formatação usa aspas duplas e indentação por espaço.

O `mypy`, em modo `strict`, o nível mais rigoroso de checagem de tipos disponível. Usa o plugin `pydantic.mypy`, necessário para entender corretamente classes que herdam de `BaseModel`. A biblioteca `zxcvbn` tem sua checagem de tipos desligada especificamente, porque ela não publica suas próprias assinaturas de tipo.

O `pytest`, configurado para reconhecer o layout "flat" do projeto (`app/` direto na raiz, não dentro de uma pasta `src/`), rodar testes `async def` sem precisar marcar cada um manualmente, e medir cobertura de código automaticamente em toda execução, mostrando no terminal quais linhas ainda não foram cobertas. A cobertura em si é restrita à pasta `app/`, deixando de fora `tests/`, `alembic/` e os próprios arquivos de configuração da contagem.

### `.env.example`

O molde do `.env` real, que nunca é commitado. Documenta cada variável de ambiente que o serviço espera: ambiente e nível de log, a URL de conexão com o banco (que aponta para o banco criado pela inicialização do Postgres ao subir o `docker-compose.yml` da raiz do monorepo), e as três variáveis do provider de LLM externo, incluindo instrução direta de onde conseguir uma chave gratuita do Ollama Cloud e como trocar para uma instância local de Ollama, caso prefira.

### `.gitignore` e `.dockerignore`

`.gitignore` lista o que nunca deve ser commitado no controle de versão: artefatos gerados pelo Python, o ambiente virtual, o `.env` real com segredos locais, e caches de ferramentas como `ruff` e `pytest`. `.dockerignore` lista o que nunca deve ser copiado para dentro da imagem Docker, mesmo existindo no diretório do build: o ambiente virtual e caches (que são reconstruídos de dentro da própria imagem via `uv`, nunca copiados do host), a pasta `tests/` inteira (testes não fazem parte da imagem de produção), o `.env` real, arquivos de controle de versão, e o próprio `README.md`, que não é necessário para o serviço rodar.

### `Dockerfile`, por dentro

A imagem é construída em dois estágios. O primeiro, `builder`, parte de uma imagem que já vem com `uv` instalado, copia primeiro `pyproject.toml` e `uv.lock`, depois o código, nessa ordem deliberada: se só o código mudar entre builds (não as dependências), a camada de cache da instalação é reaproveitada, tornando rebuilds mais rápidos. Roda `uv sync --frozen --no-dev`, instalando exatamente as versões travadas no lock file, sem as dependências de desenvolvimento. O segundo estágio parte de uma imagem Python limpa, sem `uv` nem cache de build, e copia do estágio anterior só o ambiente virtual já resolvido e o código da aplicação. É nesse segundo estágio que o usuário sem privilégio de root é criado e usado para rodar o processo, que a porta 8000 é exposta, que o `HEALTHCHECK` contra `/health` é definido, e que o comando final sobe o servidor com Uvicorn.

## Como criar um domínio novo

Copiar a estrutura de `app/modules/vault_audit/` e trocar o conteúdo:

```
modules/{novo_dominio}/
├── router.py
├── service.py
├── schemas.py
├── models.py
└── repositories/
    ├── repository.py
    └── repository_impl.py
```

Registrar o router novo em `app/api.py`. Se o domínio usar IA, o provider entra em `app/ml/providers/` seguindo o contrato de `base.py`, e o fluxo de orquestração entra em `app/ml/pipelines/`.

## Rodando localmente

Pré-requisitos: Python 3.12 ou mais recente, `uv`, Postgres rodando (o `docker-compose.yml` da raiz do monorepo sobe isso), e uma chave gratuita do Ollama Cloud, criada em ollama.com/settings/keys.

Configuração inicial:

```bash
docker compose up -d
uv sync
cp .env.example .env
```

Preencher `OLLAMA_API_KEY` no `.env` gerado.

Aplicar as migrations:

```bash
uv run alembic upgrade head
```

Subir o servidor:

```bash
uv run uvicorn app.main:app --reload
```

`GET /health` confirma que o processo e o banco estão de pé. `POST /vault-audit` audita um vault de exemplo:

```bash
curl -X POST http://localhost:8000/vault-audit \
  -H "Content-Type: application/json" \
  -d '{"user_id": "exemplo", "items": [{"item_id": "item-1", "password": "123456"}]}'
```

Rodar a suíte de testes:

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy .
```

Build e execução via Docker:

```bash
docker build -t ai_service:local .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e OLLAMA_API_KEY="..." \
  --network host \
  ai_service:local
```

A imagem é multi-stage, o estágio de build (que tem `uv`) nunca chega na imagem final, o container roda como usuário sem privilégio de root, e expõe `/health` como verificação de saúde do próprio Docker.

## Decisões de arquitetura, e por quê

O banco segue o princípio de um banco por serviço. Este serviço tem schema e usuário próprios no Postgres, nunca lê ou escreve direto nas tabelas do backend, mesmo compartilhando o mesmo container físico em desenvolvimento.

O provider de LLM usa Ollama Cloud, não outro provedor, porque o tier gratuito é permanente, sem cartão de crédito, sem custo por token, diferente de um crédito de teste que expira. O serviço faz uma chamada HTTP, não carrega nenhum modelo pesado localmente. Trocar de provedor, inclusive para uma instância local de Ollama, é mudar uma variável de ambiente, o código do provider não muda.

As tarefas em segundo plano usam o `BackgroundTasks` nativo do FastAPI, não uma fila externa como Celery com Redis, porque isso evitaria depender de infraestrutura paga para um volume de trabalho que não precisa disso. Se um domínio futuro precisar de fila resiliente a queda de processo, essa é a peça a trocar, sem precisar mudar o corpo da tarefa em si.