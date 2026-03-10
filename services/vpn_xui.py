import asyncio
import logging
import uuid

from py3xui import AsyncApi, Client

from services.vpn_base import BaseVpnProvider, VpnAccount, VpnDeleteResult, VpnStatus, VpnInbound

logger = logging.getLogger(__name__)


class XuiVpnProvider(BaseVpnProvider):

    def __init__(
        self,
        panel_url: str,
        username: str,
        password: str,
        external_ip: str,
        server_port: str,
        inbound_id: int,
        server_name: str,
    ) -> None:
        self.panel_url = panel_url
        self.username = username
        self.password = password
        self.external_ip = external_ip
        self.server_port = server_port
        self.inbound_id = inbound_id
        self.server_name = server_name

    # ------------------------------------------------------------------
    # Публичный API — реализация контракта
    # ------------------------------------------------------------------

    async def create_inbound(
            self,
            port: int,
            remark: str,
            server_name: str = "yandex.ru",
    ) -> VpnInbound:
        try:
            from py3xui.inbound import Inbound, Settings, Sniffing, StreamSettings

            api = await self._connect()
            if not api:
                return VpnInbound(success=False, error="Не удалось подключиться к панели")

            # проверяем — вдруг inbound с таким remark уже существует
            inbounds = await api.inbound.get_list()
            existing = next((i for i in inbounds if i.remark == remark), None)
            if existing:
                logger.info(f"Inbound {remark} already exists with id={existing.id}")
                return VpnInbound(success=True, inbound_id=existing.id)

            # генерируем Reality ключи
            keys = await api.server.generate_reality_keys()

            stream_settings = StreamSettings(
                security="reality",
                network="tcp",
                tcp_settings={
                    "acceptProxyProtocol": False,
                    "header": {"type": "none"},
                },
                reality_settings={
                    "show": False,
                    "dest": f"{self.server_name}:443",
                    "serverNames": [self.server_name],
                    "privateKey": keys.private_key,
                    "shortIds": [""],
                    "settings": {"publicKey": keys.public_key},
                },
            )
            inbound = Inbound(
                enable=True,
                port=port,
                protocol="vless",
                settings=Settings(),
                stream_settings=stream_settings,
                sniffing=Sniffing(enabled=True),
                remark=remark,
            )
            await api.inbound.add(inbound)

            # получаем созданный inbound чтобы узнать его id
            inbounds = await api.inbound.get_list()
            created = next((i for i in inbounds if i.remark == remark), None)
            if not created:
                return VpnInbound(success=False, error="Inbound создан но не найден в списке")

            logger.info(f"Inbound {remark} created with id={created.id}")
            return VpnInbound(success=True, inbound_id=created.id)

        except Exception as e:
            logger.error(f"create_inbound failed: {e}")
            return VpnInbound(success=False, error=str(e))

    async def delete_inbound(self, inbound_id: int) -> VpnDeleteResult:
        try:
            api = await self._connect()
            if not api:
                return VpnDeleteResult(success=False, error="Не удалось подключиться к панели")

            # идемпотентность — проверяем существует ли inbound
            inbounds = await api.inbound.get_list()
            existing = next((i for i in inbounds if i.id == inbound_id), None)
            if not existing:
                logger.info(f"Inbound {inbound_id} not found — считаем удалённым")
                return VpnDeleteResult(success=True)

            await api.inbound.delete(inbound_id)
            logger.info(f"Inbound {inbound_id} deleted")
            return VpnDeleteResult(success=True)

        except Exception as e:
            logger.error(f"delete_inbound failed: {e}")
            return VpnDeleteResult(success=False, error=str(e))

    async def create_account(
        self,
        telegram_id: int,
        expiry_days: int,
        data_limit_gb: int,
        is_trial: bool = False,
    ) -> VpnAccount:
        try:
            email = str(telegram_id)
            expiry_time = self._get_expiry_time_ms(expiry_days)
            total_bytes = self._get_data_limit_bytes(data_limit_gb)

            api = await self._connect()
            if not api:
                return VpnAccount(success=False, error="Не удалось подключиться к панели")

            inbound = await self._get_inbound(api)
            if not inbound:
                return VpnAccount(success=False, error="Inbound не найден")

            # если клиент уже существует — возвращаем его данные
            existing = await self._get_client_by_email(api, email)
            client_in_inbound = await self._get_client_from_inbound(inbound, email)

            if existing and client_in_inbound:
                logger.info(f"Client {email} already exists — returning existing data")
                connection_string = self._build_connection_string(
                    email, inbound, client_in_inbound.id
                )
                return VpnAccount(
                    success=True,
                    client_id=client_in_inbound.id,
                    connection_string=connection_string,
                    qrcode_buffer=self._create_qrcode(connection_string),
                    expiry_days=expiry_days,
                    expiry_time=existing.expiry_time,
                    is_trial=is_trial,
                )

            # создаём нового клиента
            await self._add_client(api, email, expiry_time, total_bytes)

            # даём панели время обновиться и ищем клиента
            client_in_inbound = await self._wait_for_client(api, email)

            # fallback — если клиент не найден после нескольких попыток
            # создаём connection_string с временным uuid
            client_id = client_in_inbound.id if client_in_inbound else str(uuid.uuid4())
            expiry_time_result = expiry_time

            if not client_in_inbound:
                # обновляем inbound после ожидания
                inbound = await self._get_inbound(api)
                logger.warning(f"Client {email} not found after retries — using temp uuid")

            connection_string = self._build_connection_string(email, inbound, client_id)

            return VpnAccount(
                success=True,
                client_id=client_id,
                connection_string=connection_string,
                qrcode_buffer=self._create_qrcode(connection_string),
                expiry_days=expiry_days,
                expiry_time=expiry_time_result,
                is_trial=is_trial,
            )

        except Exception as e:
            logger.error(f"create_account failed for {telegram_id}: {e}")
            return VpnAccount(success=False, error=str(e))

    async def renew_account(
        self,
        telegram_id: int,
        expiry_days: int,
        data_limit_gb: int,
    ) -> VpnAccount:
        try:
            email = str(telegram_id)
            expiry_time = self._get_expiry_time_ms(expiry_days)
            total_bytes = self._get_data_limit_bytes(data_limit_gb)

            api = await self._connect()
            if not api:
                return VpnAccount(success=False, error="Не удалось подключиться к панели")

            # если клиента нет — создаём
            existing = await self._get_client_by_email(api, email)
            if not existing:
                logger.info(f"Client {email} not found for renewal — creating new")
                return await self.create_account(telegram_id, expiry_days, data_limit_gb)

            # обновляем существующего
            updated = await self._update_client(api, email, expiry_time, total_bytes)
            if not updated:
                return VpnAccount(success=False, error="Не удалось обновить клиента")

            inbound = await self._get_inbound(api)
            client_in_inbound = await self._get_client_from_inbound(inbound, email)
            client_id = client_in_inbound.id if client_in_inbound else str(uuid.uuid4())

            connection_string = self._build_connection_string(email, inbound, client_id)

            return VpnAccount(
                success=True,
                client_id=client_id,
                connection_string=connection_string,
                qrcode_buffer=self._create_qrcode(connection_string),
                expiry_days=expiry_days,
                expiry_time=expiry_time,
            )

        except Exception as e:
            logger.error(f"renew_account failed for {telegram_id}: {e}")
            return VpnAccount(success=False, error=str(e))

    async def get_status(self, telegram_id: int) -> VpnStatus:
        try:
            email = str(telegram_id)

            api = await self._connect()
            if not api:
                return VpnStatus(success=False, error="Не удалось подключиться к панели")

            client = await self._get_client_by_email(api, email)
            if not client:
                return VpnStatus(success=False, error="Клиент не найден")

            inbound = await self._get_inbound(api)
            client_in_inbound = await self._get_client_from_inbound(inbound, email)
            client_id = client_in_inbound.id if client_in_inbound else ""

            # вычисляем оставшиеся дни
            expiry_days = self._get_expiry_days(client.expiry_time)

            return VpnStatus(
                success=True,
                client_id=client_id,
                is_active=client.enable,
                expiry_days=expiry_days,
            )

        except Exception as e:
            logger.error(f"get_status failed for {telegram_id}: {e}")
            return VpnStatus(success=False, error=str(e))

    async def delete_account(self, telegram_id: int) -> VpnDeleteResult:
        try:
            email = str(telegram_id)

            api = await self._connect()
            if not api:
                return VpnDeleteResult(success=False, error="Не удалось подключиться к панели")

            client = await self._get_client_by_email(api, email)
            if not client:
                # идемпотентность — клиента нет, считаем успехом
                return VpnDeleteResult(success=True)

            inbound = await self._get_inbound(api)
            client_in_inbound = await self._get_client_from_inbound(inbound, email)
            if not client_in_inbound:
                return VpnDeleteResult(success=True)

            await api.client.delete(self.inbound_id, client_in_inbound.id)
            logger.info(f"Client {email} deleted")
            return VpnDeleteResult(success=True)

        except Exception as e:
            logger.error(f"delete_account failed for {telegram_id}: {e}")
            return VpnDeleteResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Приватные методы — детали реализации 3x-ui
    # Снаружи не видны, handler их не вызывает никогда
    # ------------------------------------------------------------------

    async def _connect(self) -> AsyncApi | None:
        try:
            api = AsyncApi(self.panel_url, self.username, self.password)
            await api.login()
            logger.info("Connected to 3x-ui panel")
            return api
        except Exception as e:
            logger.error(f"3x-ui connection failed: {e}")
            return None

    async def _get_inbound(self, api: AsyncApi):
        try:
            inbound = await api.inbound.get_by_id(self.inbound_id)
            return inbound
        except Exception as e:
            logger.error(f"get_inbound failed: {e}")
            return None

    async def _get_client_by_email(self, api: AsyncApi, email: str):
        try:
            return await api.client.get_by_email(email)
        except Exception:
            return None

    async def _get_client_from_inbound(self, inbound, email: str):
        try:
            if not inbound or not hasattr(inbound, "settings"):
                return None
            for client in inbound.settings.clients:
                if hasattr(client, "email") and client.email == email:
                    return client
            return None
        except Exception as e:
            logger.error(f"get_client_from_inbound failed: {e}")
            return None

    async def _add_client(
        self,
        api: AsyncApi,
        email: str,
        expiry_time: int,
        total_bytes: int,
    ) -> bool:
        try:
            new_client = Client(
                id=str(uuid.uuid4()),
                email=email,
                enable=True,
                flow="xtls-rprx-vision",
                expiry_time=expiry_time,
                total_gb=total_bytes,
            )
            await api.client.add(self.inbound_id, [new_client])
            logger.info(f"Client {email} added")
            return True
        except Exception as e:
            logger.error(f"add_client failed: {e}")
            return False

    async def _update_client(
        self,
        api: AsyncApi,
        email: str,
        expiry_time: int,
        total_bytes: int,
    ):
        try:
            client = await api.client.get_by_email(email)
            if not client:
                return None

            inbound = await self._get_inbound(api)
            client_in_inbound = await self._get_client_from_inbound(inbound, email)
            if not client_in_inbound:
                return None

            client.total_gb = total_bytes
            client.expiry_time = expiry_time
            client.id = client_in_inbound.id

            await api.client.update(client.id, client)
            logger.info(f"Client {email} updated")
            return client
        except Exception as e:
            logger.error(f"update_client failed: {e}")
            return None

    async def _wait_for_client(self, api: AsyncApi, email: str, attempts: int = 3):
        """Ждём пока панель синхронизирует нового клиента"""
        await asyncio.sleep(2)
        for attempt in range(attempts):
            inbound = await self._get_inbound(api)
            client = await self._get_client_from_inbound(inbound, email)
            if client:
                logger.info(f"Client {email} found on attempt {attempt + 1}")
                return client
            logger.warning(f"Client {email} not found, attempt {attempt + 1}/{attempts}")
            await asyncio.sleep(1)
        return None

    def _build_connection_string(self, email: str, inbound, client_uuid: str) -> str:
        """Строит VLESS Reality строку подключения"""
        reality = inbound.stream_settings.reality_settings
        public_key = reality.get("settings", {}).get("publicKey", "")
        website_name = reality.get("serverNames", [""])[0]
        short_id = reality.get("shortIds", [""])[0]
        remark = inbound.remark

        return (
            f"vless://{client_uuid}@{self.external_ip}:{self.server_port}"
            f"?type=tcp&security=reality&pbk={public_key}&fp=firefox"
            f"&sni={website_name}&sid={short_id}&spx=%2F#{remark}-{email}"
        )

    def _get_expiry_days(self, expiry_time_ms: int) -> int | str:
        """Вычисляет оставшиеся дни из timestamp ms"""
        if expiry_time_ms == 0:
            return "Не ограничено"
        from datetime import datetime
        now_ms = int(datetime.now().timestamp() * 1000)
        delta_ms = expiry_time_ms - now_ms
        days = delta_ms // (1000 * 60 * 60 * 24)
        return max(0, days + 1)
