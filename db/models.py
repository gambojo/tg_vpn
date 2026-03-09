from datetime import datetime
from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from tg_core import Base, UserMixin, TimestampMixin


# ------------------------------------------------------------------
# Пользователь
# Расширяем базовую модель полями специфичными для VPN сервиса
# ------------------------------------------------------------------
class User(UserMixin, Base):
    trial_used: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    balance: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    # relationship — удобный доступ к подпискам через user.subscriptions
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user",
        order_by="Subscription.created_at.desc()",
        lazy="selectin",
    )

    @property
    def active_subscription(self) -> "Subscription | None":
        """Текущая активная подписка"""
        for sub in self.subscriptions:
            if sub.is_active:
                return sub
        return None


# ------------------------------------------------------------------
# Подписка
# Хранит историю всех подписок пользователя
# connection_string здесь а не в User — один юзер может иметь
# несколько подписок последовательно
# ------------------------------------------------------------------
class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[str] = mapped_column(
        nullable=False,                # UUID клиента на VPN сервере
    )
    connection_string: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    expiry_time: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,                # timestamp в ms, 0 = безлимит
    )
    is_trial: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        nullable=False,                # xui | outline | amnezia
        default="xui",
    )

    # relationship — доступ к юзеру через subscription.user
    user: Mapped["User"] = relationship(
        back_populates="subscriptions",
    )

    @property
    def expiry_days(self) -> int | str:
        """Осталось дней до истечения подписки"""
        if self.expiry_time == 0:
            return "Не ограничено"
        now_ms = int(datetime.now().timestamp() * 1000)
        delta_ms = self.expiry_time - now_ms
        days = delta_ms // (1000 * 60 * 60 * 24)
        return max(0, days + 1)


# ------------------------------------------------------------------
# Pre-action лог
# Фиксируем пройденные шаги чтобы не показывать их повторно
# например пользователь уже смотрел рекламу сегодня
# ------------------------------------------------------------------
class PreActionLog(TimestampMixin, Base):
    __tablename__ = "pre_action_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_type: Mapped[str] = mapped_column(
        nullable=False,                # ad | channel | stars_payment
    )
    completed_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.now,
    )
