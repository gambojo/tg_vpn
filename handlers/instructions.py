import logging

from aiogram import F, Router
from aiogram.types import Message

from handlers.start import MAIN_MENU_BUTTONS
from tg_core import main_menu, url_button

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📚 Инструкции")
async def handle_instructions(message: Message) -> None:
    await message.answer(
        "📚 <b>Инструкции по подключению</b>\n\n"
        "Выберите вашу платформу 👇",
        reply_markup=main_menu([
            "📱 Android",
            "🍎 iOS",
            "🖥 Windows",
            "🍏 macOS",
            "🏠 Главное меню",
        ]),
    )


@router.message(F.text == "📱 Android")
async def handle_android(message: Message) -> None:
    await message.answer(
        "📱 <b>Подключение на Android</b>\n\n"
        "<b>Шаг 1.</b> Установите приложение V2RayNG\n\n"
        "<b>Шаг 2.</b> Откройте бота и нажмите\n"
        "«📱 Моё подключение»\n\n"
        "<b>Шаг 3.</b> В V2RayNG нажмите ➕\n"
        "и выберите «Сканировать QR-код»\n\n"
        "<b>Шаг 4.</b> Отсканируйте QR-код из бота\n\n"
        "<b>Шаг 5.</b> Нажмите кнопку подключения ▶️",
        reply_markup=url_button(
            "📥 Скачать V2RayNG",
            "https://play.google.com/store/apps/details?id=com.v2ray.ang",
        ),
    )


@router.message(F.text == "🍎 iOS")
async def handle_ios(message: Message) -> None:
    await message.answer(
        "🍎 <b>Подключение на iOS</b>\n\n"
        "<b>Шаг 1.</b> Установите приложение Streisand\n\n"
        "<b>Шаг 2.</b> Откройте бота и нажмите\n"
        "«📱 Моё подключение»\n\n"
        "<b>Шаг 3.</b> Скопируйте строку подключения\n\n"
        "<b>Шаг 4.</b> В Streisand нажмите ➕\n"
        "и выберите «Импорт из буфера обмена»\n\n"
        "<b>Шаг 5.</b> Нажмите кнопку подключения ▶️",
        reply_markup=url_button(
            "📥 Скачать Streisand",
            "https://apps.apple.com/app/streisand/id6450534064",
        ),
    )


@router.message(F.text == "🖥 Windows")
async def handle_windows(message: Message) -> None:
    await message.answer(
        "🖥 <b>Подключение на Windows</b>\n\n"
        "<b>Шаг 1.</b> Установите приложение Nekoray\n\n"
        "<b>Шаг 2.</b> Откройте бота и нажмите\n"
        "«📱 Моё подключение»\n\n"
        "<b>Шаг 3.</b> Скопируйте строку подключения\n\n"
        "<b>Шаг 4.</b> В Nekoray нажмите «Add»\n"
        "и выберите «From clipboard»\n\n"
        "<b>Шаг 5.</b> Нажмите кнопку подключения ▶️",
        reply_markup=url_button(
            "📥 Скачать Nekoray",
            "https://github.com/MatsuriDayo/nekoray/releases",
        ),
    )


@router.message(F.text == "🍏 macOS")
async def handle_macos(message: Message) -> None:
    await message.answer(
        "🍏 <b>Подключение на macOS</b>\n\n"
        "<b>Шаг 1.</b> Установите приложение V2RayXS\n\n"
        "<b>Шаг 2.</b> Откройте бота и нажмите\n"
        "«📱 Моё подключение»\n\n"
        "<b>Шаг 3.</b> Скопируйте строку подключения\n\n"
        "<b>Шаг 4.</b> В V2RayXS нажмите ➕\n"
        "и выберите «Import from clipboard»\n\n"
        "<b>Шаг 5.</b> Нажмите кнопку подключения ▶️",
        reply_markup=url_button(
            "📥 Скачать V2RayXS",
            "https://apps.apple.com/app/v2rayxs/id1619126536",
        ),
    )


@router.message(F.text == "🏠 Главное меню")
async def handle_back_to_main(message: Message) -> None:
    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu(MAIN_MENU_BUTTONS),
    )
