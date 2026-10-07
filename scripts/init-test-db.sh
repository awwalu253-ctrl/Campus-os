#!/bin/bash
set -e

# Create the test database if it doesn't already exist.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE campusos_test OWNER campusos'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'campusos_test')\gexec
EOSQL

# Enable PostGIS in the test database.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "campusos_test" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS postgis;
EOSQL

echo "campusos_test created with PostGIS."