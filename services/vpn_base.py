from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BytesIO


# ------------------------------------------------------------------
# Универсальные dataclass'ы — результаты операций
# Одинаковы для всех провайдеров — handler никогда не видит
# детали реализации конкретного провайдера
# ------------------------------------------------------------------

@dataclass
class VpnAccount:
    """Результат создания или продления аккаунта"""
    success: bool
    client_id: str = ""
    connection_string: str = ""
    qrcode_buffer: BytesIO | None = None
    expiry_days: int = 0
    expiry_time: int = 0               # timestamp в ms, 0 = безлимит
    is_trial: bool = False
    error: str | None = None


@dataclass
class VpnStatus:
    """Результат проверки статуса аккаунта"""
    success: bool
    client_id: str = ""
    is_active: bool = False
    expiry_days: int | str = 0
    error: str | None = None


@dataclass
class VpnDeleteResult:
    """Результат удаления аккаунта"""
    success: bool
    error: str | None = None


# ------------------------------------------------------------------
# Абстрактный провайдер — контракт который должна реализовать
# каждая конкретная реализация (xui, outline, amnezia и др.)
#
# Правила контракта:
#   — методы никогда не бросают исключения наружу
#   — при ошибке возвращают dataclass с success=False и error=str
#   — telegram_id используется как уникальный идентификатор клиента
#   — expiry_days=0 означает безлимитный срок
#   — data_limit_gb=0 означает безлимитный трафик
# ------------------------------------------------------------------
class BaseVpnProvider(ABC):

    @abstractmethod
    async def create_account(
        self,
        telegram_id: int,
        expiry_days: int,
        data_limit_gb: int,
        is_trial: bool = False,
    ) -> VpnAccount:
        """
        Создать новый VPN аккаунт.
        Если аккаунт уже существует — вернуть его данные.
        """

    @abstractmethod
    async def renew_account(
        self,
        telegram_id: int,
        expiry_days: int,
        data_limit_gb: int,
    ) -> VpnAccount:
        """
        Продлить существующий VPN аккаунт.
        Если аккаунта нет — создать новый.
        """

    @abstractmethod
    async def get_status(
        self,
        telegram_id: int,
    ) -> VpnStatus:
        """
        Получить текущий статус аккаунта.
        Если аккаунта нет — вернуть success=False.
        """

    @abstractmethod
    async def delete_account(
        self,
        telegram_id: int,
    ) -> VpnDeleteResult:
        """
        Удалить аккаунт с VPN сервера.
        Если аккаунта нет — вернуть success=True (идемпотентно).
        """

    # ------------------------------------------------------------------
    # Вспомогательные методы — общие для всех провайдеров
    # Реализованы здесь чтобы не дублировать в каждой реализации
    # ------------------------------------------------------------------
    def _get_expiry_time_ms(self, expiry_days: int) -> int:
        """Конвертирует дни в timestamp ms для VPN сервера"""
        if expiry_days == 0:
            return 0
        from datetime import datetime, timedelta
        expire_dt = datetime.now() + timedelta(days=expiry_days)
        return int(expire_dt.timestamp() * 1000)

    def _get_data_limit_bytes(self, data_limit_gb: int) -> int:
        """Конвертирует GB в байты для VPN сервера"""
        if data_limit_gb == 0:
            return 0
        return data_limit_gb * 1024 * 1024 * 1024

    def _create_qrcode(self, connection_string: str) -> BytesIO | None:
        """Генерирует QR-код в памяти из строки подключения"""
        try:
            import qrcode
            import io

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(connection_string)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"QR code generation failed: {e}")
            return None
