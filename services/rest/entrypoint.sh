#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL to be ready..."

# Ждём с помощью pg_isready
while ! pg_isready -h "$COS_POSTGRES_CONTAINER" -p "$COS_POSTGRES_PORT" -U "$COS_POSTGRES_USER" -d "$COS_POSTGRES_DB"; do
  echo "🟡 PostgreSQL is still starting up... waiting 2 seconds"
  sleep 2
done

echo "✅ PostgreSQL is ready!"

echo "🚀 Running Alembic migrations..."
alembic upgrade head

echo "🔥 Starting Uvicorn..."
exec "$@"
