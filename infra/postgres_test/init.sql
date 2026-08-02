-- Mesma lógica de infra/postgres/init.sql, mas para o Postgres
-- isolado usado pela suíte de testes — nunca o mesmo banco usado em
-- desenvolvimento, para que rodar os testes não suje dado real.

CREATE USER backend_user WITH PASSWORD 'backend_test_password';
CREATE DATABASE backend_test_db OWNER backend_user;

CREATE USER ai_service_user WITH PASSWORD 'ai_service_test_password';
CREATE DATABASE ai_service_test_db OWNER ai_service_user;