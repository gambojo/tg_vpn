from datetime import datetime
from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from tgbotcore import Base, UserMixin, TimestampMixin, PreActionLog  # PreActionLog из ядра


class User(UserMixin, Base):
    trial_used: Mapped[bool] = mapped_column(default=False, nullable=False)
    balance: Mapped[int] = mapped_column(default=0, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user",
        order_by="Subscription.created_at.desc()",
        lazy="selectin",
    )

    @property
    def active_subscription(self) -> "Subscription | None":
        for sub in self.subscriptions:
            if sub.is_active:
                return sub
        return None


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[str] = mapped_column(nullable=False)
    connection_string: Mapped[str] = mapped_column(Text, nullable=False)
    expiry_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_trial: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(nullable=False, default="xui")

    user: Mapped["User"] = relationship(back_populates="subscriptions")

    @property
    def expiry_days(self) -> int | str:
        if self.expiry_time == 0:
            return "Не ограничено"
        now_ms = int(datetime.now().timestamp() * 1000)
        delta_ms = self.expiry_time - now_ms
        days = delta_ms // (1000 * 60 * 60 * 24)
        return max(0, days + 1)


# PreActionLog определён в ядре — импортируется выше
__all__ = ["User", "Subscription", "PreActionLog"]
