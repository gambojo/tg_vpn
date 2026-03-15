import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import Subscription
from handlers.start import MAIN_MENU_BUTTONS
from tgbotcore import main_menu

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "👤 Личный кабинет")
async def handle_profile(message: Message, user, session: AsyncSession) -> None:
    # считаем количество подписок пользователя
    result = await session.execute(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.user_id == user.id)
    )
    total_subs = result.scalar() or 0

    sub = user.active_subscription
    sub_status = (
        f"✅ Активна, осталось {sub.expiry_days} дней"
        if sub
        else "❌ Нет активной подписки"
    )

    await message.answer(
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"👤 Имя: <b>{user.full_name}</b>\n"
        f"📅 Зарегистрирован: <b>{user.created_at.strftime('%d.%m.%Y')}</b>\n\n"
        f"📦 <b>Подписка</b>\n"
        f"Статус: {sub_status}\n"
        f"Всего подписок: <b>{total_subs}</b>\n\n"
        f"🏆 <b>Баллы</b>\n"
        f"Баланс: <b>{user.balance} баллов</b>\n\n"
        f"👥 <b>Реферальная программа</b>\n"
        f"Ваша ссылка:\n"
        f"<code>https://t.me/{(await message.bot.get_me()).username}"
        f"?start={user.telegram_id}</code>",
        reply_markup=main_menu(MAIN_MENU_BUTTONS),
    )
