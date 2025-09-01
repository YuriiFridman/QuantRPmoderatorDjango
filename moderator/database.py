import asyncpg
import ssl
import certifi
from django.conf import settings
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class ModerationTask:
    task_type: str
    user_id: int
    username: Optional[str]
    reason: str
    chat_id: int
    moderator_id: int


class DatabaseManager:
    def __init__(self):
        self.pool = None

    async def init_db(self):
        """Инициализация подключения к БД - точно как в вашем боте"""
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            if settings.DATABASES['default']['OPTIONS'].get('sslmode') == 'require':
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED

            self.pool = await asyncpg.create_pool(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                database=settings.DATABASES['default']['NAME'],
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD'],
                ssl=ssl_context if settings.DATABASES['default']['OPTIONS'].get('sslmode') == 'require' else None,
                min_size=1,
                max_size=10
            )
        except Exception as e:
            print(f"Database connection error: {e}")
            raise

    async def add_ban(self, user_id: int, chat_id: int, reason: str):
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO bans (user_id, chat_id, reason) VALUES ($1, $2, $3) "
                "ON CONFLICT (user_id, chat_id) DO UPDATE SET reason = $3",
                user_id, chat_id, reason
            )

    async def remove_ban(self, user_id: int, chat_id: int):
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM bans WHERE user_id = $1 AND chat_id = $2",
                user_id, chat_id
            )

    async def add_warning(self, user_id: int, chat_id: int) -> int:
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            # Увеличиваем счетчик предупреждений
            result = await conn.fetchrow(
                """INSERT INTO warnings (user_id, chat_id, warn_count)
                   VALUES ($1, $2, 1) ON CONFLICT (user_id, chat_id) DO
                UPDATE SET warn_count = warnings.warn_count + 1
                    RETURNING warn_count""",
                user_id, chat_id
            )
            return result['warn_count']

    async def remove_warning(self, user_id: int, chat_id: int) -> int:
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                """UPDATE warnings
                   SET warn_count = GREATEST(0, warn_count - 1)
                   WHERE user_id = $1
                     AND chat_id = $2 RETURNING warn_count""",
                user_id, chat_id
            )
            return result['warn_count'] if result else 0

    async def get_warning_count(self, user_id: int, chat_id: int) -> int:
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT warn_count FROM warnings WHERE user_id = $1 AND chat_id = $2",
                user_id, chat_id
            )
            return result['warn_count'] if result else 0

    async def is_moderator(self, user_id: int) -> bool:
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT user_id FROM moderators WHERE user_id = $1",
                user_id
            )
            return result is not None

    async def add_moderator_to_db(self, user_id: int, username: str = None):
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO moderators (user_id, username) VALUES ($1, $2) "
                "ON CONFLICT (user_id) DO UPDATE SET username = $2",
                user_id, username
            )

    async def remove_moderator_from_db(self, user_id: int):
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM moderators WHERE user_id = $1",
                user_id
            )

    async def get_filter_status(self, chat_id: int) -> bool:
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT filter_enabled FROM chat_settings WHERE chat_id = $1",
                chat_id
            )
            return result['filter_enabled'] if result else True

    async def set_filter_status(self, chat_id: int, enabled: bool):
        """Точно как в вашем боте"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_settings (chat_id, filter_enabled) VALUES ($1, $2) "
                "ON CONFLICT (chat_id) DO UPDATE SET filter_enabled = $2",
                chat_id, enabled
            )

    async def add_punishment(self, user_id: int, chat_id: int, punishment_type: str,
                             reason: str, moderator_id: int, duration_minutes: int = None):
        """Добавление записи в таблицу punishments"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO punishments (user_id, chat_id, punishment_type, reason, moderator_id, duration_minutes)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                user_id, chat_id, punishment_type, reason, moderator_id, duration_minutes
            )

    async def get_user_punishments(self, user_id: int, chat_id: int = None) -> List[Dict]:
        """Получение истории наказаний пользователя"""
        async with self.pool.acquire() as conn:
            query = """
                    SELECT p.*, m.username as moderator_username
                    FROM punishments p
                             LEFT JOIN moderators m ON p.moderator_id = m.user_id
                    WHERE p.user_id = $1 \
                    """
            params = [user_id]

            if chat_id:
                query += " AND p.chat_id = $2"
                params.append(chat_id)

            query += " ORDER BY p.timestamp DESC"

            results = await conn.fetch(query, *params)
            return [dict(row) for row in results]

    async def get_moderation_stats(self, chat_id: int = None, days: int = 30) -> Dict:
        """Статистика модерации"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT 
                    punishment_type,
                    COUNT(*) as count,
                    DATE(timestamp) as date
                FROM punishments 
                WHERE timestamp >= NOW() - INTERVAL '%s days'
            """ % days

            params = []
            if chat_id:
                query += " AND chat_id = $1"
                params.append(chat_id)

            query += " GROUP BY punishment_type, DATE(timestamp) ORDER BY date DESC"

            results = await conn.fetch(query, *params)
            return [dict(row) for row in results]


# Создаем глобальный экземпляр
db_manager = DatabaseManager()