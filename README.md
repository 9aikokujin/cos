# Cosmeya

Платформа для мониторинга и аналитики каналов в TikTok, YouTube, Instagram и Likee. Состоит из FastAPI backend'а, парсеров на Playwright, Telegram mini app на React и вспомогательных сервисов (RabbitMQ, Postgres, ClickHouse/ELK по желанию).

## Основные компоненты
- `services/rest` — FastAPI + SQLAlchemy + Pydantic v2, Alembic, APScheduler, pika/httpx. Управляет пользователями, каналами, прокси/аккаунтами, видео и историей, раздаёт статику `/api/v1/uploads`.
- Планировщик внутри REST — по cron кладёт задачи на парсинг в очереди RabbitMQ `parsing_{tiktok|youtube|instagram|likee}`; создаёт очередь `parsing` и аплоады в volume `cos_uploads`.
- `services/parsers/*` — воркеры для TikTok/Reels/Shorts/Likee на Playwright + aio-pika + httpx. Читают очереди, собирают метрики и отправляют в REST `/api/v1/videos` (+ загрузка превью). В TikTok парсере базовый URL API захардкожен в `core/parser.py` (поменяйте при другом домене).
- `services/web` — Vite + React 19 mini-app для Telegram (`@telegram-apps/sdk`), Zustand, React Router, Chart.js, Framer Motion.
- `services/bot` — бот на aiogram 3, общается через RabbitMQ.
- `infra/*` — docker-compose для локалки и прод. Поднимает Postgres, RabbitMQ, ClickHouse (опционально), Logstash -> Elasticsearch -> Kibana (опционально). В `infra/local` сервисы фронта и парсеров закомментированы; `analytics-api` указан, но в репо нет итоговой версии (есть `services/analytics.trash`).

## Как это работает
- Авторизация через Telegram WebApp: backend принимает `Authorization: Bearer <initData>` (строка `initData` из веб-приложения Telegram). При первом старте создаётся админ с `TELEGRAM_ADMIN_ID`.
- Пользователи/каналы/прокси/аккаунты управляются REST API `/api/v1/*`. Создание/обновление каналов запускает планировщик.
- APScheduler дважды в день (12:00 и 21:00 МСК с равномерными сдвигами) отправляет задания в RabbitMQ; Instagram обрабатывается пакетами, можно снять блокировку через `/api/v1/instagram-batch/release`.
- Парсеры берут задачи из очередей, парсят канал, отправляют метрики и превью в REST. История просмотров/лайков сохраняется в таблице `video_history` (Postgres).
- Логи могут уходить в Logstash -> Elasticsearch -> Kibana, если сервисы включены.

## Основные библиотеки
- Backend: FastAPI, SQLAlchemy 2.x (async), Alembic, Pydantic v2, APScheduler, httpx, pika, python-multipart, uvicorn.
- Parsers: Playwright (+playwright-stealth), aio-pika, httpx/requests, tenacity, tqdm.
- Frontend: React 19 + Vite, @telegram-apps/sdk(/react), React Router, Zustand, Chart.js, Framer Motion, axios.
- Bot: aiogram 3, aio-pika.

2. Запустите: `docker compose -f infra/local/docker-compose.yml up --build`.
   - `rest-api` дождётся Postgres, применит Alembic миграции и стартует на `8005`.
   - При отсутствии исходников `analytics-api` удалите/закомментируйте сервис, иначе билд упадёт.
3. Для прод используйте `infra/production/docker-compose.yml` (там включены парсеры, бот и RabbitMQ).

## Запуск без Docker
- **REST API**
  ```
  cd services/rest
  python -m venv .venv
  .\.venv\Scripts\activate  # или source .venv/bin/activate
  pip install -r requirements.txt
  # создайте .env (можно взять services/rest/.env как пример) с DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, COS_RABBITMQ_*, COS_LOGSTASH_*
  alembic upgrade head
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```
- **Парсеры** (пример TikTok)
  ```
  cd services/parsers/tiktok
  python -m venv .venv && .\.venv\Scripts\activate
  pip install -r requirements.txt
  python -m playwright install --with-deps
  cat > .env <<'EOF'
  RABBITMQ_URL=amqp://cos_user:cos_password@localhost/
  CLICKHOUSE_URL=http://localhost:8123
  LOGSTASH_HOST=localhost
  LOGSTASH_PORT=5044
  EOF
  python main.py
  ```
  Убедитесь, что очередь совпадает (`parsing_tiktok` и т.п.) и что базовый URL API в парсере указывает на ваш backend.
- **Frontend**
  ```
  cd services/web
  yarn install
  VITE_API_URL=http://localhost:8005/api/v1 yarn dev --host --port 4444
  ```

## Регистрация и работа с API
- Базовый префикс: `/api/v1`, OpenAPI: `http://localhost:8005/docs`.
- Админ создаётся автоматически из `TELEGRAM_ADMIN_ID`.
- Авторизация: `Authorization: Bearer <telegram_init_data>` (initData из Telegram WebApp).
- Регистрация нового пользователя:
  ```
  curl -X POST http://localhost:8005/api/v1/users/register \
    -H "Authorization: Bearer <initData>" \
    -H "Content-Type: application/json" \
    -d '{"username":"demo_user","nickname":"Demo"}'
  ```
- Получить себя: `GET /api/v1/users/me`.
- Добавить канал: `POST /api/v1/channels` тело `{"type":"tiktok","link":"https://www.tiktok.com/@user","name_channel":"User"}`.
- Прокси/аккаунты: `POST /api/v1/proxies` (поле `proxy_str`, `for_likee` для Likee), `POST /api/v1/accounts` (поле `account_str`).
- Видео наполняются парсерами; превью можно положить вручную через `POST /api/v1/videos/{id}/upload-image/`.
- Сбросить зависший Instagram batch: `POST /api/v1/instagram-batch/release` с `{"batch_id":"<id>"}`.
- Загруженные файлы доступны по `/api/v1/uploads/...`.

