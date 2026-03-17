from tgbotcore import PreActionService, PreActionStates, StepType

pre_action = PreActionService(
    steps=settings.PRE_ACTION_STEPS,
    is_step_skippable=lambda user, step_type: (
        step_type == StepType.STARS_PAYMENT
        and user.active_subscription is not None
    ),
)


# Pre-action callbacks
@router.callback_query(F.data == "pre_action:ad_continue")
async def handle_ad_continue(
    callback: CallbackQuery,
    state,
    user,
    session: AsyncSession,
) -> None:
    await pre_action.continue_ad(user, state, session)
    await callback.message.delete()

    data = await state.get_data()
    pending_action = data.get("pending_action")

    if pending_action == "get_vpn":
        await _do_get_vpn(callback.message, user, session)
    elif pending_action == "renew_vpn":
        await _do_renew_vpn(callback.message, user, session)

    await callback.answer()


@router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message,
    state,
    user,
    session: AsyncSession,
) -> None:
    payment = message.successful_payment
    logger.info(
        f"Payment from {user.telegram_id}: "
        f"{payment.total_amount} {payment.currency}"
    )

    # читаем ДО clear
    data = await state.get_data()
    pending_action = data.get("pending_action", "get_vpn")

    await pre_action.handle_payment(
        user=user,
        payment_id=payment.telegram_payment_charge_id,
        amount=payment.total_amount,
        state=state,
        session=session,
    )

    await message.answer("✅ Оплата получена! Создаём подключение...")

    if pending_action == "renew_vpn":
        await _do_renew_vpn(message, user, session)
    else:
        await _do_get_vpn(message, user, session)
