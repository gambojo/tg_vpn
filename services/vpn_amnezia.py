import logging
from base64 import b64encode

import httpx

from services.vpn_base import BaseVpnProvider, VpnAccount, VpnDeleteResult, VpnStatus, VpnInbound

logger = logging.getLogger(__name__)


class AmneziaWGAPI:
    """
    Async HTTP клиент для amneziawg-web-ui API.
    https://github.com/AlexisHW/amneziawg-web-ui

    Аутентификация — HTTP Basic Auth (NGINX_USER / NGINX_PASSWORD).
    """

    def __init__(
        self,
        base_url: str,
        username: str = "admin",
        password: str = "changeme",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        credentials = b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {credentials}",
        }

    async def _get(self, path: str):
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}{path}", headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json: dict | None = None):
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}{path}",
                json=json or {},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    async def _delete(self, path: str):
        async with httpx.AsyncClient() as client:
            r = await client.delete(f"{self.base_url}{path}", headers=self._headers)
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    async def health(self) -> bool:
        try:
            data = await self._get("/api/system/status")
            return isinstance(data, dict)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Clients
    # ------------------------------------------------------------------

    async def list_clients(self, server_id: str) -> list[dict]:
        return await self._get(f"/api/servers/{server_id}/clients")

    async def add_client(self, server_id: str, name: str) -> dict:
        """Возвращает {"id": "...", "name": "...", ...}"""
        return await self._post(f"/api/servers/{server_id}/clients", {"name": name})

    async def get_client_config(self, server_id: str, client_id: str) -> str:
        """Возвращает конфиг клиента в виде текста (.conf формат)."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/api/servers/{server_id}/clients/{client_id}/config",
                headers=self._headers,
            )
            r.raise_for_status()
            return r.text

    async def delete_client(self, server_id: str, client_id: str) -> dict:
        return await self._delete(f"/api/servers/{server_id}/clients/{client_id}")

    async def find_client_by_name(self, server_id: str, name: str) -> dict | None:
        """Ищет клиента по имени — возвращает None если не найден."""
        try:
            clients = await self.list_clients(server_id)
            return next((c for c in clients if c.get("name") == name), None)
        except Exception:
            return None


class AmneziaVpnProvider(BaseVpnProvider):
    """
    VPN провайдер для AmneziaWG через amneziawg-web-ui.

    AmneziaWG не управляет сроками подписки — expiry_time
    вычисляется локально и хранится только в БД бота.
    """

    def __init__(
        self,
        api_url: str,
        server_id: str,
        username: str = "admin",
        password: str = "changeme",
    ) -> None:
        self.api = AmneziaWGAPI(base_url=api_url, username=username, password=password)
        self.server_id = server_id

    async def create_inbound(self, port: int, remark: str, server_name: str = "yandex.ru") -> VpnInbound:
        """Серверы управляются через веб-интерфейс — no-op."""
        logger.info("AmneziaWG: create_inbound is a no-op")
        return VpnInbound(success=True, inbound_id=0)

    async def delete_inbound(self, inbound_id: int) -> VpnDeleteResult:
        """no-op."""
        logger.info("AmneziaWG: delete_inbound is a no-op")
        return VpnDeleteResult(success=True)

    async def create_account(
        self,
        telegram_id: int,
        expiry_days: int,
        data_limit_gb: int,
        is_trial: bool = False,
    ) -> VpnAccount:
        try:
            name = str(telegram_id)

            existing = await self.api.find_client_by_name(self.server_id, name)
            if existing:
                logger.info(f"AmneziaWG: client {name} already exists")
                config = await self.api.get_client_config(self.server_id, existing["id"])
                return VpnAccount(
                    success=True,
                    client_id=existing["id"],
                    connection_string=config,
                    qrcode_buffer=self._create_qrcode(config),
                    expiry_days=expiry_days,
                    expiry_time=self._get_expiry_time_ms(expiry_days),
                    is_trial=is_trial,
                )

            result = await self.api.add_client(self.server_id, name)
            client_id = result["id"]
            config = await self.api.get_client_config(self.server_id, client_id)

            logger.info(f"AmneziaWG: client {name} created id={client_id}")
            return VpnAccount(
                success=True,
                client_id=client_id,
                connection_string=config,
                qrcode_buffer=self._create_qrcode(config),
                expiry_days=expiry_days,
                expiry_time=self._get_expiry_time_ms(expiry_days),
                is_trial=is_trial,
            )

        except Exception as e:
            logger.error(f"AmneziaWG: create_account failed for {telegram_id}: {e}")
            return VpnAccount(success=False, error=str(e))

    async def renew_account(
        self,
        telegram_id: int,
        expiry_days: int,
        data_limit_gb: int,
    ) -> VpnAccount:
        """Конфиг при продлении не меняется — только expiry_time в БД."""
        try:
            name = str(telegram_id)

            existing = await self.api.find_client_by_name(self.server_id, name)
            if not existing:
                return await self.create_account(telegram_id, expiry_days, data_limit_gb)

            config = await self.api.get_client_config(self.server_id, existing["id"])
            logger.info(f"AmneziaWG: client {name} renewed")
            return VpnAccount(
                success=True,
                client_id=existing["id"],
                connection_string=config,
                qrcode_buffer=self._create_qrcode(config),
                expiry_days=expiry_days,
                expiry_time=self._get_expiry_time_ms(expiry_days),
            )

        except Exception as e:
            logger.error(f"AmneziaWG: renew_account failed for {telegram_id}: {e}")
            return VpnAccount(success=False, error=str(e))

    async def get_status(self, telegram_id: int) -> VpnStatus:
        try:
            name = str(telegram_id)
            existing = await self.api.find_client_by_name(self.server_id, name)

            if not existing:
                return VpnStatus(success=False, error="Клиент не найден")

            return VpnStatus(
                success=True,
                client_id=existing["id"],
                is_active=True,
                expiry_days=0,  # срок только в БД
            )

        except Exception as e:
            logger.error(f"AmneziaWG: get_status failed for {telegram_id}: {e}")
            return VpnStatus(success=False, error=str(e))

    async def delete_account(self, telegram_id: int) -> VpnDeleteResult:
        try:
            name = str(telegram_id)
            existing = await self.api.find_client_by_name(self.server_id, name)

            if not existing:
                return VpnDeleteResult(success=True)

            await self.api.delete_client(self.server_id, existing["id"])
            logger.info(f"AmneziaWG: client {name} deleted")
            return VpnDeleteResult(success=True)

        except Exception as e:
            logger.error(f"AmneziaWG: delete_account failed for {telegram_id}: {e}")
            return VpnDeleteResult(success=False, error=str(e))
