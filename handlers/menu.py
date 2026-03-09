from aiogram import F, Router
from aiogram.types import Message

router = Router()


@router.message(F.text == "ℹ️ О боте")
async def about(message: Message) -> None:
    await message.answer(
        "🤖 <b>О боте</b>\n\n"
        "Этот бот создан на базе tg-core — "
        "библиотеки для быстрого старта Telegram-ботов.\n\n"
        "GitHub: github.com/you/tg-core"
    )


@router.message(F.text == "📞 Контакты")
async def contacts(message: Message) -> None:
    await message.answer(
        "📞 <b>Контакты</b>\n\n"
        "По всем вопросам: @your_username"
    )
