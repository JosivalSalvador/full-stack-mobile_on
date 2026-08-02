-- Executado uma única vez, na primeira inicialização do volume do
-- Postgres de desenvolvimento. Cria um banco e um usuário isolados
-- por serviço ("database per service"): nenhum serviço lê ou escreve
-- diretamente nas tabelas de outro.

CREATE USER backend_user WITH PASSWORD 'backend_dev_password';
CREATE DATABASE backend_db OWNER backend_user;

CREATE USER ai_service_user WITH PASSWORD 'ai_service_dev_password';
CREATE DATABASE ai_service_db OWNER ai_service_user;