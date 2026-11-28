-- Create (or bring up to date) one project's database and roles on the shared PostgreSQL.
-- Idempotent: rerunning it only resets the passwords and grants.
--
--   docker exec -i pg psql -U postgres -v ON_ERROR_STOP=1 \
--     -v project=dndsheet -v owner_password="$OWNER_PW" -v app_password="$APP_PW" \
--     -f - < create-project.sql
--
-- Two roles per project, neither of them superuser, CREATEDB or CREATEROLE:
--   <project>      owns the database and its `public` schema; runs migrations and data copies;
--   <project>_app  what the app connects as: data only (SELECT/INSERT/UPDATE/DELETE), no DDL,
--                  a connection limit and a statement timeout, so one project can't starve the rest.
-- Other projects' roles can't connect to this database (CONNECT is revoked from PUBLIC).

\set app :project '_app'

SELECT format('CREATE ROLE %I LOGIN', :'project')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'project') \gexec
SELECT format('CREATE ROLE %I LOGIN', :'app')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app') \gexec

SELECT format('ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 5 PASSWORD %L',
              :'project', :'owner_password') \gexec
SELECT format('ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 10 PASSWORD %L',
              :'app', :'app_password') \gexec
SELECT format('ALTER ROLE %I SET statement_timeout = %L', :'app', '30s') \gexec

SELECT format('CREATE DATABASE %I OWNER %I TEMPLATE template0 ENCODING %L LOCALE_PROVIDER builtin BUILTIN_LOCALE %L',
              :'project', :'project', 'UTF8', 'C.UTF-8')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'project') \gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'project') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'project', :'app') \gexec
-- Nobody but the superuser gets into the maintenance database.
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;

\connect :project
-- Tables the owner creates later (migrations) are readable and writable by the app role.
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
              :'project', :'app') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I',
              :'project', :'app') \gexec
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I', :'app') \gexec
SELECT format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', :'app') \gexec
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
