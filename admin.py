import logging
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Subscription, User
from services.vpn_service import vpn

logger = logging.getLogger(__name__)
router = Router()


# ------------------------------------------------------------------
# /vpn_stats — статистика подписок
# ------------------------------------------------------------------
@router.message(Command("vpn_stats"))
async def cmd_vpn_stats(message: Message, user, session: AsyncSession) -> None:
    if not user.is_admin:
        return

    # всего подписок
    total = await session.scalar(
        select(func.count()).select_from(Subscription)
    )

    # активных подписок
    active = await session.scalar(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.is_active == True)    # noqa: E712
    )

    # триальных подписок
    trial = await session.scalar(
        select(func.count())
        .select_from(Subscription)
        .where(
            Subscription.is_active == True,       # noqa: E712
            Subscription.is_trial == True,        # noqa: E712
        )
    )

    # подписок истекающих в ближайшие 3 дня
    now_ms = int(datetime.now().timestamp() * 1000)
    from datetime import timedelta
    in_3_days_ms = int(
        (datetime.now() + timedelta(days=3)).timestamp() * 1000
    )
    expiring_soon = await session.scalar(
        select(func.count())
        .select_from(Subscription)
        .where(
            Subscription.is_active == True,       # noqa: E712
            Subscription.expiry_time > now_ms,
            Subscription.expiry_time <= in_3_days_ms,
        )
    )

    # подписок по провайдерам
    providers_result = await session.execute(
        select(Subscription.provider, func.count())
        .where(Subscription.is_active == True)    # noqa: E712
        .group_by(Subscription.provider)
    )
    providers = providers_result.all()
    providers_text = "\n".join(
        f"  • {provider}: <b>{count}</b>"
        for provider, count in providers
    ) or "  • нет данных"

    await message.answer(
        f"📊 <b>Статистика подписок</b>\n\n"
        f"📦 Всего подписок: <b>{total}</b>\n"
        f"✅ Активных: <b>{active}</b>\n"
        f"🎁 Триальных: <b>{trial}</b>\n"
        f"⚠️ Истекают через 3 дня: <b>{expiring_soon}</b>\n\n"
        f"🔌 <b>По провайдерам:</b>\n"
        f"{providers_text}",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------
# /vpn_delete <telegram_id> — удалить VPN аккаунт пользователя
# ------------------------------------------------------------------
@router.message(Command("vpn_delete"))
async def cmd_vpn_delete(
    message: Message,
    user,
    session: AsyncSession,
) -> None:
    if not user.is_admin:
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Использование: /vpn_delete &lt;telegram_id&gt;")
        return

    telegram_id = int(args[1])

    # ищем юзера
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        await message.answer("❌ Пользователь не найден.")
        return

    # удаляем с VPN сервера
    delete_result = await vpn.delete_account(telegram_id)
    if not delete_result.success:
        await message.answer(
            f"❌ Не удалось удалить аккаунт с VPN сервера.\n"
            f"Ошибка: {delete_result.error}"
        )
        return

    # деактивируем подписки в БД
    subs_result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == target.id,
            Subscription.is_active == True,       # noqa: E712
        )
    )
    subs = subs_result.scalars().all()
    for sub in subs:
        sub.is_active = False

    await message.answer(
        f"✅ VPN аккаунт пользователя "
        f"<b>{target.full_name}</b> "
        f"(<code>{telegram_id}</code>) удалён.",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------
# /vpn_info <telegram_id> — информация о VPN аккаунте
# ------------------------------------------------------------------
@router.message(Command("vpn_info"))
async def cmd_vpn_info(
    message: Message,
    user,
    session: AsyncSession,
) -> None:
    if not user.is_admin:
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Использование: /vpn_info &lt;telegram_id&gt;")
        return

    telegram_id = int(args[1])

    # ищем юзера
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        await message.answer("❌ Пользователь не найден.")
        return

    # статус с VPN сервера
    status = await vpn.get_status(telegram_id)

    # активная подписка из БД
    sub_result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == target.id,
            Subscription.is_active == True,       # noqa: E712
        )
    )
    sub = sub_result.scalar_one_or_none()

    if not status.success or not sub:
        await message.answer(
            f"👤 <b>{target.full_name}</b> "
            f"(<code>{telegram_id}</code>)\n\n"
            f"❌ Нет активного VPN аккаунта.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"👤 <b>{target.full_name}</b> "
        f"(<code>{telegram_id}</code>)\n\n"
        f"📦 <b>VPN аккаунт</b>\n"
        f"Статус: {'✅ Активен' if status.is_active else '❌ Неактивен'}\n"
        f"Осталось дней: <b>{status.expiry_days}</b>\n"
        f"Провайдер: <b>{sub.provider}</b>\n"
        f"Триал: {'✅' if sub.is_trial else '❌'}\n"
        f"Создана: <b>{sub.created_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
        f"🔑 Строка подключения:\n"
        f"<code>{sub.connection_string}</code>",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------
# Доп. статистика для create_admin_router
# ------------------------------------------------------------------
async def get_vpn_stats() -> str:
    """
    Передаётся в create_admin_router как stats_callback.
    Добавляет VPN статистику к базовой статистике /stats.
    """
    from tgbotcore import get_session_factory
    factory = get_session_factory()

    async with factory() as session:
        active = await session.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.is_active == True)    # noqa: E712
        )
        trial = await session.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(
                Subscription.is_active == True,       # noqa: E712
                Subscription.is_trial == True,        # noqa: E712
            )
        )

    return (
        f"📦 Активных подписок: <b>{active}</b>\n"
        f"🎁 Из них триальных: <b>{trial}</b>"
    )
