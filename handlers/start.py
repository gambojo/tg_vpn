import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from tg_core import main_menu

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
async def cmd_start(message: Message, user) -> None:
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
