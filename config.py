from tgbotcore import Settings
from pydantic import field_validator


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

    # ------------------------------------------------------------------
    # Telegram Stars оплата
    # ------------------------------------------------------------------
    PAYMENT_ENABLED: bool = False
    PAYMENT_AMOUNT: int = 50           # в Stars
    PAYMENT_DESCRIPTION: str = "VPN подписка на 30 дней"

    # ------------------------------------------------------------------
    # Pre-action хук — шаги перед выдачей VPN
    # порядок в списке = порядок выполнения
    # ------------------------------------------------------------------
    PRE_ACTION_STEPS: list[dict] = [
        {
            "type": "ad",
            "enabled": False,
            "text": "Наш партнёр — SuperVPN Pro 🚀",
            "duration": 5,
        },
        {
            "type": "channel",
            "enabled": False,
            "channel": "@my_channel",
            "message": "Подпишитесь на наш канал чтобы продолжить",
        },
        {
            "type": "stars_payment",
            "enabled": False,
            "amount": 50,
            "description": "VPN подписка на 30 дней",
        },
    ]

    # ------------------------------------------------------------------
    # Напоминания об истечении подписки
    # ------------------------------------------------------------------
    NOTIFY_DAYS_BEFORE: list[int] = [3, 1]  # за сколько дней напоминать

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
