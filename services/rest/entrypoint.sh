set -e

echo "⏳ Ждем готовности PostgreSQL..."

while ! pg_isready -h "$COS_POSTGRES_CONTAINER" -p "$COS_POSTGRES_PORT" -U "$COS_POSTGRES_USER" -d "$COS_POSTGRES_DB"; do
  echo "PostgreSQL еще не готов, ждем 2 секунды"
  sleep 2
done

echo "PostgreSQL готов!"

echo "Запуск миграций Alembic..."
alembic upgrade head

echo "Запуск Uvicorn..."
exec "$@"
