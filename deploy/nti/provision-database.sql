-- Executar como DBA conectado ao banco postgres, fora de uma transação.
-- Nomes fictícios: ajustar antes de executar. Senha definida interativamente no psql.
CREATE ROLE pcirn LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
SET password_encryption = 'scram-sha-256';
\password pcirn
CREATE DATABASE pcirn OWNER pcirn ENCODING 'UTF8' TEMPLATE template0;
REVOKE ALL ON DATABASE pcirn FROM PUBLIC;
GRANT CONNECT ON DATABASE pcirn TO pcirn;
\connect pcirn
ALTER SCHEMA public OWNER TO pcirn;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO pcirn;
-- Não criar tabelas nem instalar extensões antes da importação: o dump as contém.
-- Extensões não confiáveis no dump exigem revisão/provisionamento específico pelo DBA.
