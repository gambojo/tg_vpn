import logging

from aiogram import F, Router
from aiogram.types import BufferedInputFile, Message, CallbackQuery, SuccessfulPayment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import Subscription
from services.pre_action import PreActionService, PreActionStates
from services.vpn_service import vpn
from tg_core import back_button

from handlers.start import MAIN_MENU_BUTTONS
from tg_core import main_menu

logger = logging.getLogger(__name__)
router = Router()

# ------------------------------------------------------------------
# Глобальный экземпляр хука — читает шаги из конфига один раз
# ------------------------------------------------------------------
pre_action = PreActionService(steps=settings.PRE_ACTION_STEPS)


# ------------------------------------------------------------------
# Вспомогательные функции
# ------------------------------------------------------------------
async def _send_vpn_result(message: Message, account, session: AsyncSession, user) -> None:
    """Сохраняет подписку в БД и отправляет результат пользователю"""

    # деактивируем старые подписки
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.is_active == True,    # noqa: E712
        )
    )
    old_subs = result.scalars().all()
    for sub in old_subs:
        sub.is_active = False

    # сохраняем новую подписку
    sub = Subscription(
        user_id=user.id,
        client_id=account.client_id,
        connection_string=account.connection_string,
        expiry_time=account.expiry_time,
        is_trial=account.is_trial,
        is_active=True,
        provider=settings.VPN_PROVIDER,
    )
    session.add(sub)
    await session.flush()

    # отправляем результат
    await message.answer(
        f"✅ <b>VPN активирован!</b>\n\n"
        f"📅 Срок действия: <b>{account.expiry_days} дней</b>\n"
        f"🔑 Строка подключения:\n"
        f"<code>{account.connection_string}</code>",
        reply_markup=main_menu(MAIN_MENU_BUTTONS),
    )

    if account.qrcode_buffer:
        photo = BufferedInputFile(
            account.qrcode_buffer.getvalue(),
            filename="qrcode.png",
        )
        await message.answer_photo(photo, caption="📱 QR-код для подключения")


# ------------------------------------------------------------------
# 🚀 Получить VPN
# ------------------------------------------------------------------
@router.message(F.text == "🚀 Получить VPN")
async def handle_get_vpn(
    message: Message,
    state,
    user,
    session: AsyncSession,
) -> None:
    # сохраняем целевое действие в FSM — после прохождения хука
    # знаем что делать дальше
    from aiogram.fsm.context import FSMContext
    await state.update_data(pending_action="get_vpn")

    result = await pre_action.execute(user, message, state, session)
    if not result.completed:
        return

    await _do_get_vpn(message, user, session)


async def _do_get_vpn(message: Message, user, session: AsyncSession) -> None:
    """Выдаёт VPN после прохождения всех шагов хука"""

    # проверяем есть ли активная подписка
    existing = user.active_subscription
    if existing:
        await message.answer(
            f"ℹ️ У вас уже есть активная подписка.\n\n"
            f"📅 Осталось дней: <b>{existing.expiry_days}</b>\n\n"
            f"Используйте «🔄 Продлить подписку» чтобы продлить.",
            reply_markup=main_menu(MAIN_MENU_BUTTONS),
        )
        return

    # проверяем триал
    is_trial = False
    if settings.TRIAL_ENABLED and not user.trial_used:
        is_trial = True
        user.trial_used = True
        await message.answer(
            f"🎁 <b>Активируем бесплатный пробный период!</b>\n\n"
            f"⏳ Срок: {settings.TRIAL_DAYS} дней\n"
            f"Подождите несколько секунд...",
        )
        expiry_days = settings.TRIAL_DAYS
    else:
        await message.answer("⏳ Создаём VPN подключение, подождите...")
        expiry_days = settings.EXPIRY_DAYS

    account = await vpn.create_account(
        telegram_id=user.telegram_id,
        expiry_days=expiry_days,
        data_limit_gb=settings.DATA_LIMIT_GB,
        is_trial=is_trial,
    )

    if not account.success:
        await message.answer(
            f"❌ Не удалось создать VPN подключение.\n"
            f"Ошибка: {account.error}\n\n"
            f"Попробуйте позже или обратитесь в поддержку.",
            reply_markup=main_menu(MAIN_MENU_BUTTONS),
        )
        return

    await _send_vpn_result(message, account, session, user)


# ------------------------------------------------------------------
# 🔄 Продлить подписку
# ------------------------------------------------------------------
@router.message(F.text == "🔄 Продлить подписку")
async def handle_renew_vpn(
    message: Message,
    state,
    user,
    session: AsyncSession,
) -> None:
    await state.update_data(pending_action="renew_vpn")

    result = await pre_action.execute(user, message, state, session)
    if not result.completed:
        return

    await _do_renew_vpn(message, user, session)


async def _do_renew_vpn(message: Message, user, session: AsyncSession) -> None:
    """Продлевает VPN после прохождения всех шагов хука"""
    await message.answer("⏳ Продлеваем подписку, подождите...")

    account = await vpn.renew_account(
        telegram_id=user.telegram_id,
        expiry_days=settings.EXPIRY_DAYS,
        data_limit_gb=settings.DATA_LIMIT_GB,
    )

    if not account.success:
        await message.answer(
            f"❌ Не удалось продлить подписку.\n"
            f"Ошибка: {account.error}\n\n"
            f"Попробуйте позже или обратитесь в поддержку.",
            reply_markup=main_menu(MAIN_MENU_BUTTONS),
        )
        return

    await _send_vpn_result(message, account, session, user)


# ------------------------------------------------------------------
# 📊 Статус подписки
# ------------------------------------------------------------------
@router.message(F.text == "📊 Статус подписки")
async def handle_status(message: Message, user) -> None:
    sub = user.active_subscription

    if not sub:
        await message.answer(
            "❌ У вас нет активной подписки.\n\n"
            "Нажмите «🚀 Получить VPN» чтобы начать.",
            reply_markup=main_menu(MAIN_MENU_BUTTONS),
        )
        return

    await message.answer(
        f"📊 <b>Статус подписки</b>\n\n"
        f"✅ Подписка активна\n"
        f"📅 Осталось дней: <b>{sub.expiry_days}</b>\n"
        f"🔌 Провайдер: <b>{sub.provider}</b>\n"
        f"📆 Создана: <b>{sub.created_at.strftime('%d.%m.%Y')}</b>",
        reply_markup=main_menu(MAIN_MENU_BUTTONS),
    )


# ------------------------------------------------------------------
# 📱 Моё подключение
# ------------------------------------------------------------------
@router.message(F.text == "📱 Моё подключение")
async def handle_my_connection(message: Message, user) -> None:
    sub = user.active_subscription

    if not sub:
        await message.answer(
            "❌ У вас нет активной подписки.\n\n"
            "Нажмите «🚀 Получить VPN» чтобы начать.",
            reply_markup=main_menu(MAIN_MENU_BUTTONS),
        )
        return

    await message.answer(
        f"📱 <b>Данные подключения</b>\n\n"
        f"🔑 Строка подключения:\n"
        f"<code>{sub.connection_string}</code>",
        reply_markup=main_menu(MAIN_MENU_BUTTONS),
    )

    # генерируем QR-код на лету из сохранённой строки
    from services.vpn_base import BaseVpnProvider
    qr_buffer = BaseVpnProvider._create_qrcode(
        BaseVpnProvider, sub.connection_string
    )
    if qr_buffer:
        photo = BufferedInputFile(qr_buffer.getvalue(), filename="qrcode.png")
        await message.answer_photo(photo, caption="📱 QR-код для подключения")


# ------------------------------------------------------------------
# Pre-action callbacks
# ------------------------------------------------------------------
@router.callback_query(F.data == "pre_action:check_channel")
async def handle_check_channel(
    callback: CallbackQuery,
    state,
    user,
    session: AsyncSession,
) -> None:
    """Пользователь нажал 'Проверить подписку' на канал"""
    result = await pre_action.check_channel(user, callback.message, state, session)

    if not result.completed:
        await callback.answer()
        return

    # канал проверен — выполняем отложенное действие
    await callback.message.delete()
    data = await state.get_data()
    pending_action = data.get("pending_action")

    if pending_action == "get_vpn":
        await _do_get_vpn(callback.message, user, session)
    elif pending_action == "renew_vpn":
        await _do_renew_vpn(callback.message, user, session)

    await callback.answer()


@router.callback_query(F.data == "pre_action:cancel")
async def handle_pre_action_cancel(
    callback: CallbackQuery,
    state,
) -> None:
    """Пользователь отменил прохождение хука"""
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()


# ------------------------------------------------------------------
# Telegram Stars — успешная оплата
# ------------------------------------------------------------------
@router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message,
    state,
    user,
    session: AsyncSession,
) -> None:
    """Telegram Stars оплата прошла успешно"""
    payment: SuccessfulPayment = message.successful_payment
    logger.info(
        f"Successful payment from {user.telegram_id}: "
        f"{payment.total_amount} {payment.currency}"
    )

    # логируем шаг оплаты
    from services.pre_action import StepType
    from db.models import PreActionLog
    from datetime import datetime
    log = PreActionLog(
        user_id=user.id,
        step_type=StepType.STARS_PAYMENT,
        completed_at=datetime.now(),
    )
    session.add(log)

    await state.clear()

    # выполняем отложенное действие
    data = await state.get_data()
    pending_action = data.get("pending_action", "get_vpn")

    await message.answer("✅ Оплата получена! Создаём подключение...")

    if pending_action == "renew_vpn":
        await _do_renew_vpn(message, user, session)
    else:
        await _do_get_vpn(message, user, session)
