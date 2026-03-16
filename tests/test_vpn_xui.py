from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from services.vpn_xui import XuiVpnProvider


@pytest.fixture
def provider():
    return XuiVpnProvider(
        panel_url="http://fake-panel:54321",
        username="admin",
        password="password",
        external_ip="1.2.3.4",
        server_port="443",
        inbound_id=1,
        server_name="yandex.ru",
    )


def make_client(email: str, client_id: str = "uuid-123"):
    """Создаёт мок клиента py3xui."""
    c = MagicMock()
    c.id = client_id
    c.email = email
    c.enable = True
    c.expiry_time = 0
    return c


def make_inbound(clients: list):
    """Создаёт мок inbound py3xui."""
    inbound = MagicMock()
    inbound.remark = "test-inbound"
    inbound.stream_settings.reality_settings = {
        "settings": {"publicKey": "pubkey123"},
        "serverNames": ["yandex.ru"],
        "shortIds": ["abc"],
    }
    inbound.settings.clients = clients
    return inbound


def make_api(inbound=None, client=None):
    """Создаёт мок AsyncApi."""
    api = MagicMock()
    api.login = AsyncMock()
    api.inbound.get_by_id = AsyncMock(return_value=inbound)
    api.client.get_by_email = AsyncMock(return_value=client)
    api.client.add = AsyncMock()
    api.client.update = AsyncMock()
    api.client.delete = AsyncMock()
    return api


@pytest.mark.asyncio
async def test_create_account_new_client(provider):
    """Создание нового клиента."""
    client = make_client("123456", "uuid-123")
    inbound = make_inbound([client])

    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(inbound=inbound, client=None)
        # первый get_by_email — нет клиента
        # после add — клиент появляется
        api.client.get_by_email = AsyncMock(return_value=None)
        MockApi.return_value = api

        # _wait_for_client найдёт клиента с первой попытки
        with patch("services.vpn_xui.asyncio.sleep", new_callable=AsyncMock):
            result = await provider.create_account(
                telegram_id=123456,
                expiry_days=30,
                data_limit_gb=0,
            )

    assert result.success is True
    assert result.client_id == "uuid-123"
    assert "vless://" in result.connection_string
    api.client.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_account_existing_client(provider):
    """Идемпотентность — клиент уже существует."""
    client = make_client("123456", "uuid-123")
    inbound = make_inbound([client])

    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(inbound=inbound, client=client)
        MockApi.return_value = api

        result = await provider.create_account(123456, 30, 0)

    assert result.success is True
    assert result.client_id == "uuid-123"
    api.client.add.assert_not_called()


@pytest.mark.asyncio
async def test_renew_account_existing(provider):
    """Продление существующего клиента."""
    client = make_client("123456", "uuid-123")
    inbound = make_inbound([client])

    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(inbound=inbound, client=client)
        MockApi.return_value = api

        result = await provider.renew_account(123456, 30, 0)

    assert result.success is True
    assert result.client_id == "uuid-123"
    api.client.update.assert_called_once()


@pytest.mark.asyncio
async def test_renew_account_not_found(provider):
    """Продление — клиента нет, создаём нового."""
    client = make_client("123456", "uuid-123")
    inbound = make_inbound([client])

    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(inbound=inbound, client=None)
        MockApi.return_value = api

        with patch("services.vpn_xui.asyncio.sleep", new_callable=AsyncMock):
            result = await provider.renew_account(123456, 30, 0)

    assert result.success is True
    api.client.add.assert_called_once()


@pytest.mark.asyncio
async def test_delete_account(provider):
    """Удаление клиента."""
    client = make_client("123456", "uuid-123")
    inbound = make_inbound([client])

    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(inbound=inbound, client=client)
        MockApi.return_value = api

        result = await provider.delete_account(123456)

    assert result.success is True
    api.client.delete.assert_called_once_with(1, "uuid-123")


@pytest.mark.asyncio
async def test_delete_account_not_found(provider):
    """Идемпотентность — клиента нет, не падаем."""
    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(client=None)
        MockApi.return_value = api

        result = await provider.delete_account(999999)

    assert result.success is True
    api.client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_get_status(provider):
    """Статус активного клиента."""
    client = make_client("123456", "uuid-123")
    inbound = make_inbound([client])

    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(inbound=inbound, client=client)
        MockApi.return_value = api

        result = await provider.get_status(123456)

    assert result.success is True
    assert result.is_active is True
    assert result.client_id == "uuid-123"


@pytest.mark.asyncio
async def test_get_status_not_found(provider):
    """Статус — клиента нет."""
    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = make_api(client=None)
        MockApi.return_value = api

        result = await provider.get_status(999999)

    assert result.success is False


@pytest.mark.asyncio
async def test_connect_failure(provider):
    """Панель недоступна — возвращаем success=False."""
    with patch("services.vpn_xui.AsyncApi") as MockApi:
        api = MagicMock()
        api.login = AsyncMock(side_effect=Exception("Connection refused"))
        MockApi.return_value = api

        result = await provider.create_account(123456, 30, 0)

    assert result.success is False
    assert result.error is not None
