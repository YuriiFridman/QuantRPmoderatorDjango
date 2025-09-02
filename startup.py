from moderator.database import db_manager

async def init_database():
    # Більше не ініціалізуємо пул на старті.
    # Пулі створюються ліниво у відповідному event loop при першому зверненні.
    return

async def shutdown_database():
    # Опційно викликайте це у lifespan/shutdown, щоб закрити всі пулі
    await db_manager.close_all()