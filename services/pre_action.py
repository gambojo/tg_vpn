import logging
from datetime import datetime, timedelta
from enum import StrEnum

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PreActionLog

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Типы шагов
# ------------------------------------------------------------------
class StepType(StrEnum):
    AD = "ad"
    CHANNEL = "channel"
    STARS_PAYMENT = "stars_payment"


# ------------------------------------------------------------------
# FSM состояния хука
# ------------------------------------------------------------------
class PreActionStates(StatesGroup):
    waiting_channel_check = State()    # ждём нажатия "Проверить подписку"
    waiting_payment = State()          # ждём successful_payment апдейт


# ------------------------------------------------------------------
# Результат выполнения хука
# ------------------------------------------------------------------
class PreActionResult:
    def __init__(self, completed: bool, step_type: str | None = None):
        self.completed = completed       # True — все шаги пройдены
        self.step_type = step_type       # какой шаг остановил выполнение


# ------------------------------------------------------------------
# Сервис
# ------------------------------------------------------------------
class PreActionService:
    """
    Универсальный хук перед целевым действием.
    Выполняет шаги из конфига последовательно.
    Если шаг не пройден — останавливает выполнение и ждёт следующего апдейта.

    Использование в handler'е:
        result = await pre_action.execute(user, message, state, session)
        if not result.completed:
            return   # хук сам отправил нужное сообщение пользователю
        # все шаги пройдены — выполняем целевое действие
    """

    def __init__(self, steps: list[dict]) -> None:
        # фильтруем только включённые шаги
        self.steps = [s for s in steps if s.get("enabled", False)]

    async def execute(
        self,
        user,
        message: Message,
        state: FSMContext,
        session: AsyncSession,
    ) -> PreActionResult:
        """Выполняет все шаги последовательно"""

        if not self.steps:
            return PreActionResult(completed=True)

        for step in self.steps:
            step_type = step["type"]

            # проверяем не пройден ли уже этот шаг сегодня
            if await self._is_step_done_today(user.id, step_type, session):
                logger.info(f"Step {step_type} already done today for user {user.id}")
                continue

            result = await self._execute_step(step, user, message, state, session)

            if not result.completed:
                return result

        return PreActionResult(completed=True)

    async def check_channel(
        self,
        user,
        message: Message,
        state: FSMContext,
        session: AsyncSession,
    ) -> PreActionResult:
        """
        Повторная проверка подписки на канал.
        Вызывается когда пользователь нажал "Проверить подписку".
        """
        channel_step = next(
            (s for s in self.steps if s["type"] == StepType.CHANNEL),
            None,
        )
        if not channel_step:
            return PreActionResult(completed=True)

        is_subscribed = await self._check_channel_subscription(
            message.bot, user.telegram_id, channel_step["channel"]
        )

        if not is_subscribed:
            await message.answer(
                f"❌ Вы ещё не подписались на канал.\n\n"
                f"Подпишитесь и нажмите «Проверить подписку» снова."
            )
            return PreActionResult(completed=False, step_type=StepType.CHANNEL)

        # подписка подтверждена — логируем и завершаем шаг
        await self._log_step(user.id, StepType.CHANNEL, session)
        await state.clear()
        return PreActionResult(completed=True)

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    async def _execute_step(
        self,
        step: dict,
        user,
        message: Message,
        state: FSMContext,
        session: AsyncSession,
    ) -> PreActionResult:
        step_type = step["type"]

        if step_type == StepType.AD:
            return await self._execute_ad(step, user, message, session)

        elif step_type == StepType.CHANNEL:
            return await self._execute_channel(step, user, message, state)

        elif step_type == StepType.STARS_PAYMENT:
            return await self._execute_stars_payment(step, user, message, state)

        else:
            logger.warning(f"Unknown step type: {step_type} — skipping")
            return PreActionResult(completed=True)

    async def _execute_ad(
        self,
        step: dict,
        user,
        message: Message,
        session: AsyncSession,
    ) -> PreActionResult:
        """Показывает рекламное сообщение"""
        import asyncio

        text = step.get("text", "")
        duration = step.get("duration", 5)

        await message.answer(
            f"📺 <b>Рекламное сообщение</b>\n\n"
            f"{text}\n\n"
            f"⏳ Пожалуйста, подождите {duration} сек...",
        )
        await asyncio.sleep(duration)

        # реклама просмотрена — логируем
        await self._log_step(user.id, StepType.AD, session)
        logger.info(f"Ad shown to user {user.id}")
        return PreActionResult(completed=True)

    async def _execute_channel(
        self,
        step: dict,
        user,
        message: Message,
        state: FSMContext,
    ) -> PreActionResult:
        """Проверяет подписку на канал"""
        from tgbotcore import confirm_cancel

        channel = step.get("channel", "")
        text = step.get("message", f"Подпишитесь на канал {channel}")

        is_subscribed = await self._check_channel_subscription(
            message.bot, user.telegram_id, channel
        )

        if is_subscribed:
            return PreActionResult(completed=True)

        # не подписан — показываем сообщение и ждём
        await message.answer(
            f"📢 {text}\n\n"
            f"🔗 Канал: {channel}\n\n"
            f"После подписки нажмите «Проверить подписку»",
            reply_markup=confirm_cancel(
                confirm_text="✅ Проверить подписку",
                cancel_text="❌ Отмена",
                confirm_callback="pre_action:check_channel",
                cancel_callback="pre_action:cancel",
            ),
        )
        await state.set_state(PreActionStates.waiting_channel_check)
        return PreActionResult(completed=False, step_type=StepType.CHANNEL)

    async def _execute_stars_payment(
        self,
        step: dict,
        user,
        message: Message,
        state: FSMContext,
    ) -> PreActionResult:
        """Создаёт инвойс Telegram Stars"""
        from aiogram.types import LabeledPrice

        amount = step.get("amount", 50)
        description = step.get("description", "VPN подписка")

        await message.answer_invoice(
            title="VPN подписка",
            description=description,
            payload=f"vpn_payment:{user.telegram_id}",
            currency="XTR",
            prices=[LabeledPrice(label="VPN", amount=amount)],
        )
        await state.set_state(PreActionStates.waiting_payment)
        return PreActionResult(completed=False, step_type=StepType.STARS_PAYMENT)

    async def _check_channel_subscription(
        self,
        bot,
        telegram_id: int,
        channel: str,
    ) -> bool:
        """Проверяет подписку пользователя на Telegram канал"""
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=telegram_id)
            return member.status in ("member", "administrator", "creator")
        except Exception as e:
            logger.error(f"Channel subscription check failed for {telegram_id}: {e}")
            return False

    async def _is_step_done_today(
        self,
        user_id: int,
        step_type: str,
        session: AsyncSession,
    ) -> bool:
        """Проверяет выполнялся ли шаг сегодня"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(PreActionLog).where(
                PreActionLog.user_id == user_id,
                PreActionLog.step_type == step_type,
                PreActionLog.completed_at >= today,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _log_step(
        self,
        user_id: int,
        step_type: str,
        session: AsyncSession,
    ) -> None:
        """Логирует пройденный шаг"""
        log = PreActionLog(
            user_id=user_id,
            step_type=step_type,
            completed_at=datetime.now(),
        )
        session.add(log)
        await session.flush()
