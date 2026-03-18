from tgbotcore import Settings
from pydantic import field_validator, model_validator
from typing import Any


class VpnSettings(Settings):

    # ------------------------------------------------------------------
    # VPN провайдер
    # ------------------------------------------------------------------
    VPN_PROVIDER: str = "xui"          # xui | amnezia

    # ------------------------------------------------------------------
    # XUI (3x-ui)
    # ------------------------------------------------------------------
    XUI_PANEL_URL: str = ""
    XUI_USERNAME: str = ""
    XUI_PASSWORD: str = ""
    XUI_EXTERNAL_IP: str = ""
    XUI_SERVER_PORT: str = "443"
    XUI_INBOUND_ID: int = 1
    XUI_SERVER_NAME: str = "yandex.ru"

    # ------------------------------------------------------------------
    # AmneziaWG (amneziawg-web-ui)
    # ------------------------------------------------------------------
    AWG_API_URL: str = "http://localhost:8080"
    AWG_SERVER_ID: str = ""        # ID сервера из панели, например "wg_abc123"
    AWG_USERNAME: str = "admin"    # NGINX_USER из docker-compose
    AWG_PASSWORD: str = "changeme" # NGINX_PASSWORD из docker-compose

    # ------------------------------------------------------------------
    # Параметры подписки
    # ------------------------------------------------------------------
    EXPIRY_DAYS: int = 30
    DATA_LIMIT_GB: int = 0             # 0 = безлимит

    # ------------------------------------------------------------------
    # Триальный период
    # ------------------------------------------------------------------
    TRIAL_ENABLED: bool = True
    TRIAL_DAYS: int = 3

    # поля читаются из .env
    PAYMENT_ENABLED: bool = False
    PAYMENT_AMOUNT: int = 50
    PAYMENT_DESCRIPTION: str = "VPN подписка на 30 дней"

    CHANNEL_ENABLED: bool = False
    CHANNEL_ID: str = "@my_channel"
    CHANNEL_MESSAGE: str = "Подпишитесь на наш канал чтобы продолжить"

    AD_ENABLED: bool = False
    AD_TEXT: str = "Наш партнёр — SuperVPN Pro 🚀"
    AD_BUTTON_TEXT: str = "▶️ Продолжить"
    AD_DURATION: int = 5

    # ------------------------------------------------------------------
    # Pre-action хук — шаги перед выдачей VPN
    # порядок в списке = порядок выполнения
    # ------------------------------------------------------------------
    PRE_ACTION_STEPS: list[dict] = []

    @model_validator(mode="after")
    def build_pre_action_steps(self) -> "VpnSettings":
        self.PRE_ACTION_STEPS = [
            {
                "type": "ad",
                "enabled": self.AD_ENABLED,
                "text": self.AD_TEXT,
                "button_text": self.AD_BUTTON_TEXT,
                "duration": self.AD_DURATION,
            },
            {
                "type": "channel",
                "enabled": self.CHANNEL_ENABLED,
                "channel": self.CHANNEL_ID,
                "message": self.CHANNEL_MESSAGE,
                "button_check": "✅ Проверить подписку",
                "button_cancel": "❌ Отмена",
            },
            {
                "type": "stars_payment",
                "enabled": self.PAYMENT_ENABLED,
                "amount": self.PAYMENT_AMOUNT,
                "title": "VPN подписка",
                "description": self.PAYMENT_DESCRIPTION,
            },
        ]
        return self

    # ------------------------------------------------------------------
    # Напоминания об истечении подписки
    # ------------------------------------------------------------------
    NOTIFY_DAYS_BEFORE: Any = [3, 1]

    @field_validator("NOTIFY_DAYS_BEFORE", mode="before")
    @classmethod
    def parse_notify_days(cls, v) -> list[int]:
        if isinstance(v, list):
            return [int(i) for i in v]
        if isinstance(v, str):
            v = v.strip('"\'')  # убираем кавычки если есть
            return [int(i.strip()) for i in v.split(",") if i.strip()]
        if isinstance(v, int):
            return [v]
        return v

    # ------------------------------------------------------------------
    # Валидация
    # ------------------------------------------------------------------
    @field_validator("VPN_PROVIDER")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"xui", "amnezia"}
        if v not in allowed:
            raise ValueError(f"VPN_PROVIDER must be one of {allowed}")
        return v

settings = VpnSettings()
