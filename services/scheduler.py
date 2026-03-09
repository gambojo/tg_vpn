import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Subscription, User
from tg_core import get_session_factory

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Тексты уведомлений
# ------------------------------------------------------------------
def _expiry_message(days: int) -> str:
    if days == 1:
        return (
            "⚠️ <b>Подписка истекает завтра!</b>\n\n"
            "Не забудьте продлить VPN чтобы не потерять доступ.\n"
            "Нажмите «🔄 Продлить подписку» в главном меню."
        )
    return (
        f"⏳ <b>Подписка истекает через {days} дня</b>\n\n"
        f"Продлите VPN заранее чтобы не было перерывов.\n"
        f"Нажмите «🔄 Продлить подписку» в главном меню."
    )


# ------------------------------------------------------------------
# Задачи планировщика
# ------------------------------------------------------------------
async def _notify_expiring_subscriptions(
    bot: Bot,
    notify_days: list[int],
) -> None:
    """
    Проверяет подписки которые истекают через notify_days дней
    и отправляет уведомления пользователям.
    Запускается раз в день в 10:00.
    """
    factory = get_session_factory()
    async with factory() as session:
        for days in notify_days:
            await _notify_for_days(bot, session, days)


async def _notify_for_days(
    bot: Bot,
    session: AsyncSession,
    days: int,
) -> None:
    """Уведомляет пользователей чья подписка истекает ровно через days дней"""
    now_ms = int(datetime.now().timestamp() * 1000)

    # окно: от начала дня до конца дня через days дней
    target_date = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    from datetime import timedelta
    window_start_ms = int(
        (target_date + timedelta(days=days)).timestamp() * 1000
    )
    window_end_ms = int(
        (target_date + timedelta(days=days + 1)).timestamp() * 1000
    )

    result = await session.execute(
        select(Subscription)
        .join(User, Subscription.user_id == User.id)
        .where(
            Subscription.is_active == True,        # noqa: E712
            Subscription.expiry_time > 0,          # не безлимитные
            Subscription.expiry_time >= window_start_ms,
            Subscription.expiry_time < window_end_ms,
            User.is_banned == False,               # noqa: E712
        )
    )
    subscriptions = result.scalars().all()

    sent = 0
    failed = 0

    for sub in subscriptions:
        try:
            user_result = await session.execute(
                select(User).where(User.id == sub.user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                continue

            await bot.send_message(
                chat_id=user.telegram_id,
                text=_expiry_message(days),
                parse_mode="HTML",
            )
            sent += 1

        except Exception as e:
            logger.error(
                f"Failed to notify user {sub.user_id} "
                f"about expiry in {days} days: {e}"
            )
            failed += 1

    logger.info(
        f"Expiry notifications for {days} days: "
        f"sent={sent} failed={failed}"
    )


async def _deactivate_expired_subscriptions() -> None:
    """
    Деактивирует подписки у которых истёк срок.
    Запускается раз в час.
    """
    factory = get_session_factory()
    now_ms = int(datetime.now().timestamp() * 1000)

    async with factory() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.is_active == True,    # noqa: E712
                Subscription.expiry_time > 0,      # не безлимитные
                Subscription.expiry_time < now_ms,
            )
        )
        expired = result.scalars().all()

        for sub in expired:
            sub.is_active = False

        await session.commit()

        if expired:
            logger.info(f"Deactivated {len(expired)} expired subscriptions")


# ------------------------------------------------------------------
# Инициализация планировщика
# ------------------------------------------------------------------
def create_scheduler(bot: Bot, notify_days: list[int]) -> AsyncIOScheduler:
    """
    Создаёт и настраивает планировщик.
    Вызывается один раз в main.py.

    Args:
        bot:          экземпляр Bot из main.py
        notify_days:  список дней для уведомлений из settings
    """
    scheduler = AsyncIOScheduler()

    # уведомления об истечении — каждый день в 10:00
    scheduler.add_job(
        _notify_expiring_subscriptions,
        trigger=CronTrigger(hour=10, minute=0),
        kwargs={"bot": bot, "notify_days": notify_days},
        id="notify_expiring",
        replace_existing=True,
    )

    # деактивация истёкших подписок — каждый час
    scheduler.add_job(
        _deactivate_expired_subscriptions,
        trigger=CronTrigger(minute=0),
        id="deactivate_expired",
        replace_existing=True,
    )

    return scheduler
