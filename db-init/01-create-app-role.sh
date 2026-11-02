#!/bin/bash
# Roda automaticamente só na primeira inicialização de um volume NOVO do Postgres
# (mecanismo padrão de /docker-entrypoint-initdb.d da imagem oficial).
#
# Cria o usuário de privilégio limitado que a aplicação usa (APP_DB_USER), separado
# do usuário superusuário/manutenção (POSTGRES_USER). Isso reproduz, num volume
# novo, o que foi feito manualmente via psql num volume já existente em 2026-10-24
# (ver docs/escopo_e_roteiro.md, Etapa 8).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE "$APP_DB_USER" LOGIN PASSWORD '$APP_DB_PASSWORD';
    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO "$APP_DB_USER";
    ALTER DATABASE "$POSTGRES_DB" OWNER TO "$APP_DB_USER";
    ALTER SCHEMA public OWNER TO "$APP_DB_USER";
EOSQL

# Bancos só de DESENVOLVIMENTO (o Django usa datavision_dj; os testes, datavision_dj_test). O usuário da aplicação não
# pode criar bancos (de propósito), então o banco de teste é criado aqui e reaproveitado (pytest --reuse-db).
# A produção não define DEV_DATABASES e usa só o POSTGRES_DB.
if [ "${DEV_DATABASES:-}" = "true" ]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE DATABASE datavision_dj OWNER \"$APP_DB_USER\""
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE DATABASE datavision_dj_test OWNER \"$APP_DB_USER\""
fi
