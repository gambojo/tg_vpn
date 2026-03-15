import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from tgbotcore import (
    AntiSpamMiddleware,
    UserMiddleware,
    create_admin_router,
    init_db,
    run_migrations,
)

from admin import router as vpn_admin_router
from admin import get_vpn_stats
from config import settings
from db.models import User
from handlers.instructions import router as instructions_router
from handlers.profile import router as profile_router
from handlers.start import router as start_router
from handlers.subscription import router as subscription_router
from services.scheduler import create_scheduler


logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------
    async def on_startup(bot: Bot):
        await bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Помощь"),
        ])
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.set_my_commands(
                    commands=[
                        BotCommand(command="start", description="Главное меню"),
                        BotCommand(command="help", description="Помощь"),
                        BotCommand(command="admin", description="Панель админа"),
                        BotCommand(command="vpn_stats", description="Статистика VPN"),
                        BotCommand(command="vpn_info", description="Инфо о пользователе"),
                        BotCommand(command="vpn_delete", description="Удалить VPN"),
                    ],
                    scope=BotCommandScopeChat(chat_id=admin_id),
                )
            except Exception:
                pass

    dp.startup.register(on_startup)

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------
    dp.update.middleware(AntiSpamMiddleware(
        limit=settings.RATE_LIMIT,
        window=settings.RATE_LIMIT_WINDOW,
    ))
    dp.update.middleware(UserMiddleware(
        user_model=User,
        admin_ids=settings.ADMIN_IDS,
    ))

    # ------------------------------------------------------------------
    # Роутеры
    # ------------------------------------------------------------------
    dp.include_router(
        create_admin_router(
            user_model=User,
            extra_routers=[vpn_admin_router],
            stats_callback=get_vpn_stats,
        )
    )
    dp.include_router(start_router)
    dp.include_router(subscription_router)
    dp.include_router(profile_router)
    dp.include_router(instructions_router)

    # ------------------------------------------------------------------
    # База данных
    # ------------------------------------------------------------------
    run_migrations()
    await init_db(
        database_url=settings.DATABASE_URL,
        create_tables=False,
        user_model=User,
        admin_ids=settings.ADMIN_IDS,
    )

    # ------------------------------------------------------------------
    # Планировщик
    # ------------------------------------------------------------------
    scheduler = create_scheduler(
        bot=bot,
        notify_days=settings.NOTIFY_DAYS_BEFORE,
    )
    scheduler.start()
    logger.info("Scheduler started.")

    # ------------------------------------------------------------------
    # Запуск
    # ------------------------------------------------------------------
    logger.info("Bot started.")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
