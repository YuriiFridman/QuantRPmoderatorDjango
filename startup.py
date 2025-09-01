import asyncio
from moderator.database import db_manager

async def init_database():
    """Инициализация подключения к базе данных при запуске Django"""
    await db_manager.init_db()
    print("Database connection pool initialized")