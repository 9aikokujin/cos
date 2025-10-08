from datetime import datetime
from datetime import date
from typing import Dict, Any, Optional, Union, List, Tuple
from clickhouse_connect import get_async_client
from config import config
from schema import CreateVideoView, VideoView
import asyncio

class ClickHouseClient:
    def __init__(self):
        self.client = None

    async def init(self):
        while True:
            try:
                self.client = await get_async_client(
                    host=config.CLICKHOUSE_HOST,
                    port=config.CLICKHOUSE_PORT,
                    username=config.CLICKHOUSE_USER,
                    password=config.CLICKHOUSE_PASSWORD,
                    database=config.CLICKHOUSE_DATABASE,
                    secure=False
                )
                # Проверка соединения
                await self.client.ping()
                print("✅ ClickHouse connected successfully")
                break
            except Exception as e:
                print(f"❌ Failed to connect to ClickHouse: {e}")
                print("🔁 Retrying in 5 seconds...")
                await asyncio.sleep(5)

    async def execute(self, query: str, params: dict = None):
        if self.client is None:
            raise RuntimeError("Client is not initialized. Call 'await init()' first.")
        return await self.client.query(query, params)

    async def create_views_table(self):
        if self.client is None:
            raise RuntimeError("Client is not initialized. Call 'await init()' first.")
        drop_table_sql = "DROP TABLE IF EXISTS video_views_hourly"
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS video_views_hourly (
            created_at DateTime,
            channel_id Nullable(UInt32),
            channel_type Nullable(String),
            user_id Nullable(UInt32),
            video_id String,
            video_title String,
            video_url String,
            views UInt64,
            hashtag Nullable(String),
            total_views Nullable(UInt64),
            first Boolean DEFAULT false
        ) ENGINE = MergeTree()
        ORDER BY (video_id, created_at)
        """
        # await self.client.command(drop_table_sql)
        await self.client.command(create_table_sql)

    async def get_everything(self) -> List[Tuple]:
        if self.client is None:
            raise RuntimeError("Client is not initialized. Call 'await init()' first.")

        EVERYTHING_QUERY = "SELECT * FROM video_views_hourly ORDER BY created_at DESC"
        params = {}

        try:
            # Выполняем запрос
            result = await self.client.query(EVERYTHING_QUERY, parameters=params)

            # Для clickhouse-connect результат находится в result_set
            # Преобразуем в список кортежей
            final_result = [tuple(row) for row in result.result_set]

            return final_result

        except Exception as e:
            print(f"Error executing query: {e}")
            raise

    async def get_unique_hashtags(self, user_id: Optional[int] = None) -> List[str]:
        if self.client is None:
            raise RuntimeError("Client is not initialized. Call 'await init()' first.")

        query = """
        SELECT DISTINCT hashtag
        FROM video_views_hourly
        WHERE hashtag IS NOT NULL
        AND trim(hashtag) != ''
        """
        params = {}

        if user_id is not None:
            query += " AND user_id = %(user_id)s"
            params["user_id"] = user_id

        query += " ORDER BY hashtag"

        try:
            result = await self.client.query(query, parameters=params)
            hashtags = [row[0] for row in result.result_set if row[0]]
            return hashtags
        except Exception as e:
            print(f"Error fetching unique hashtags: {e}")
            raise RuntimeError(f"Failed to fetch hashtags: {str(e)}")

    async def get_video_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        if self.client is None:
            raise RuntimeError("Client is not initialized. Call 'await init()' first.")

        query = """
        SELECT
            total_views,
            views
        FROM video_views_hourly
        WHERE video_url = %(url)s
        ORDER BY created_at DESC
        LIMIT 1
        """

        try:
            result = await self.client.query(query, parameters={"url": url})
            rows = list(result.result_set)

            if not rows:
                return None

            row = rows[0]
            return {
                "total_views": row[0],
                "views": row[1]
            }
        except Exception as e:
            print(f"Error in get_video_by_url: {e}")
            raise RuntimeError(f"Failed to fetch video by URL: {str(e)}")

    async def insert_video_views(self, data: List[CreateVideoView]):
        if self.client is None:
            raise RuntimeError("Client is not initialized. Call 'await init()' first.")

        now = datetime.utcnow()
        rows = []
        column_names = [
            'created_at',
            'channel_id',
            'channel_type',
            'user_id',
            'video_id',
            'video_title',
            'video_url',
            'views',           # delta
            'total_views',     # current total
            'first',
            'hashtag'
        ]

        for view in data:
            old_video = await self.get_video_by_url(view.video_url)
            if old_video:
                try:
                    current_views = int(view.views) if view.views is not None else 0
                    previous_total = int(old_video['total_views']) if old_video['total_views'] is not None else 0

                    delta_views = current_views - previous_total

                    if delta_views < 0:
                        logger.warning(
                            f"Views decreased for video {view.video_url}: "
                            f"{previous_total} → {current_views}. Setting delta to 0."
                        )
                        delta_views = 0

                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid views value for {view.video_url}: {e}")
                    delta_views = 0

                # ✅ Добавляем строку при наличии старой записи
                rows.append([
                    now,
                    view.channel_id,
                    view.channel_type,
                    view.user_id,
                    view.video_id,
                    view.video_title,
                    view.video_url,
                    delta_views,       # прирост
                    current_views,     # текущее общее число просмотров
                    False,             # не первый раз
                    view.hashtag
                ])
            else:
                # ✅ Ветка: видео не найдено — первый раз
                logger.info(f"Video not found in DB, treating as new: {view.video_url}")
                rows.append([
                    now,
                    view.channel_id,
                    view.channel_type,
                    view.user_id,
                    view.video_id,
                    view.video_title,
                    view.video_url,
                    view.views,        # считаем, что прирост = текущему значению
                    view.views,        # total_views
                    True,              # первый раз
                    view.hashtag
                ])

        # ✅ Вставка только если есть данные
        if rows:
            await self.client.insert(
                table='video_views_hourly',
                data=rows,
                column_names=column_names
            )
        else:
            logger.debug("No rows to insert into video_views_hourly")

    async def user_analytics_filtered(
        self,
        user_id: Optional[int],
        group_by_fields: List[str],
        filter_hashtag: Optional[str] = None,
        filter_channel_id: Optional[int] = None,
        filter_channel_type: Optional[List[str]] = None,
        filter_video_url: Optional[str] = None,
        filter_date_from: Optional[date] = None,
        filter_date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        if self.client is None:
            raise RuntimeError("Client is not initialized. Call 'await init()' first.")

        if not group_by_fields:
            raise ValueError("group_by_fields list cannot be empty.")

        supported_fields = {'day', 'hashtag', 'channel_id', 'channel_type'}
        if not set(group_by_fields).issubset(supported_fields):
            raise ValueError(f"group_by_fields can only contain: {supported_fields}")

        select_parts = []
        group_by_parts = []

        if 'day' in group_by_fields:
            select_parts.append("toDate(created_at) AS day")
            group_by_parts.append("day")
        if 'hashtag' in group_by_fields:
            select_parts.append("hashtag")
            group_by_parts.append("hashtag")
        if 'channel_id' in group_by_fields:
            select_parts.append("channel_id")
            group_by_parts.append("channel_id")
        if 'channel_type' in group_by_fields:
            select_parts.append("channel_type")
            group_by_parts.append("channel_type")

        select_clause = ",\n        ".join(select_parts)
        group_by_clause = ", ".join(group_by_parts)

        where_conditions = []
        params: Dict[str, Any] = {}

        if user_id is not None:
            where_conditions.append("user_id = %(user_id)s")
            params["user_id"] = user_id

        if filter_hashtag is not None:
            where_conditions.append("hashtag = %(filter_hashtag)s")
            params["filter_hashtag"] = filter_hashtag

        if filter_channel_id is not None:
            where_conditions.append("channel_id = %(filter_channel_id)s")
            params["filter_channel_id"] = filter_channel_id

        # 🔥 Обработка списка channel_type
        if filter_channel_type is not None and len(filter_channel_type) > 0:
            # Экранируем ключи параметров: channel_type_0, channel_type_1, ...
            type_keys = []
            for i, ctype in enumerate(filter_channel_type):
                key = f"channel_type_{i}"
                params[key] = ctype
                type_keys.append(f"%({key})s")

            # Формируем: channel_type IN (%(channel_type_0)s, %(channel_type_1)s, ...)
            where_conditions.append(f"channel_type IN ({', '.join(type_keys)})")

        if filter_video_url is not None:
            where_conditions.append("video_url = %(filter_video_url)s")
            params["filter_video_url"] = filter_video_url

        if filter_date_from is not None:
            where_conditions.append("created_at >= %(filter_date_from)s")
            params["filter_date_from"] = filter_date_from.strftime('%Y-%m-%d 00:00:00')

        if filter_date_to is not None:
            where_conditions.append("created_at <= %(filter_date_to)s")
            params["filter_date_to"] = filter_date_to.strftime('%Y-%m-%d 23:59:59')
        where_conditions.append("NOT first")
        where_part = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

        query = f"""
        SELECT
            {select_clause},
            sum(views) AS total_views
        FROM video_views_hourly
        {where_part}
        GROUP BY {group_by_clause}
        ORDER BY {group_by_parts[0] if group_by_parts else 'total_views DESC'}
        """

        try:
            result = await self.client.query(query, parameters=params)
            rows = list(result.result_set)

            formatted_result = []
            field_names = [field if field != 'day' else 'day' for field in group_by_fields] + ['total_views']

            for row in rows:
                item: Dict[str, Any] = {}
                for i, field_name in enumerate(field_names):
                    value = row[i]
                    if field_name == 'day' and value is not None:
                        item['day'] = value.strftime("%d.%m.%Y") if hasattr(value, 'strftime') else str(value)
                    else:
                        item[field_name] = value
                formatted_result.append(item)

            return formatted_result

        except Exception as e:
            print(f"Error in user_analytics_filtered: {e}")
            raise RuntimeError(f"Failed to execute analytics query: {str(e)}")
