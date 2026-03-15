import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from db.models import User

from tgbotcore import main_menu

logger = logging.getLogger(__name__)
router = Router()

# ------------------------------------------------------------------
# Кнопки главного меню
# ------------------------------------------------------------------
MAIN_MENU_BUTTONS = [
    "🚀 Получить VPN",
    "🔄 Продлить подписку",
    "📊 Статус подписки",
    "📱 Моё подключение",
    "👤 Личный кабинет",
    "📚 Инструкции",
]


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user,
    session: AsyncSession,
    is_new_user: bool,
    command: CommandObject,
) -> None:

    # обрабатываем реферальный параметр только для новых пользователей
    if is_new_user and command.args and command.args.isdigit():
        referrer_id = int(command.args)

        if referrer_id != user.telegram_id:
            # ищем реферера
            result = await session.execute(
                select(User).where(User.telegram_id == referrer_id)
            )
            referrer = result.scalar_one_or_none()

            if referrer:
                # начисляем баллы
                referrer.balance += settings.REFERRAL_BONUS
                logger.info(
                    f"Referral bonus {settings.REFERRAL_BONUS} credited "
                    f"to {referrer_id} for inviting {user.telegram_id}"
                )

                # уведомляем реферера
                try:
                    await message.bot.send_message(
                        chat_id=referrer.telegram_id,
                        text=(
                            f"🎉 По вашей реферальной ссылке зарегистрировался "
                            f"новый пользователь!\n\n"
                            f"💰 Вам начислено <b>{settings.REFERRAL_BONUS} баллов</b>.\n"
                            f"Текущий баланс: <b>{referrer.balance} баллов</b>"
                        ),
                    )
                except Exception as e:
                    logger.error(f"Failed to notify referrer {referrer_id}: {e}")

    await message.answer(
        f"👋 Привет, <b>{user.full_name}</b>!\n\n"
        f"🔒 Добро пожаловать в VPN сервис.\n\n"
        f"<b>Что умеет этот бот:</b>\n"
        f"• Быстро выдать VPN подключение\n"
        f"• Продлить существующую подписку\n"
        f"• Показать статус и остаток дней\n"
        f"• Напомнить когда подписка заканчивается\n\n"
        f"Выбери действие в меню 👇",
        reply_markup=main_menu(MAIN_MENU_BUTTONS),
    )

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📋 <b>Доступные команды</b>\n\n"
        "/start — главное меню\n"
        "/help — список команд\n\n"
        "🔘 <b>Кнопки меню</b>\n"
        "🚀 Получить VPN — выдать новое подключение\n"
        "🔄 Продлить подписку — продлить существующую\n"
        "📊 Статус подписки — сколько дней осталось\n"
        "📱 Моё подключение — строка и QR-код\n"
        "👤 Личный кабинет — баллы и реферальная ссылка\n"
        "📚 Инструкции — как подключить VPN\n\n"
        "👤 <b>Для администраторов</b>\n"
        "/stats — статистика\n"
        "/broadcast — рассылка\n"
        "/ban — заблокировать\n"
        "/unban — разблокировать\n"
        "/user — информация о пользователе\n"
        "/vpn_stats — статистика подписок",
    )
