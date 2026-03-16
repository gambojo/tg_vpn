import pytest
import respx
import httpx
from services.vpn_amnezia import AmneziaVpnProvider


@pytest.fixture
def provider():
    return AmneziaVpnProvider(
        api_url="http://fake-server:8080",
        server_id="wg_abc123",
        username="admin",
        password="password",
    )


@pytest.mark.asyncio
@respx.mock
async def test_create_account_new_client(provider):
    """Создание нового клиента."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.post("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json={"id": "client_xyz", "name": "123456"})
    )
    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients/client_xyz/config").mock(
        return_value=httpx.Response(200, text="[Interface]\nPrivateKey = abc...")
    )

    result = await provider.create_account(
        telegram_id=123456,
        expiry_days=30,
        data_limit_gb=0,
    )

    assert result.success is True
    assert result.client_id == "client_xyz"
    assert "[Interface]" in result.connection_string


@pytest.mark.asyncio
@respx.mock
async def test_create_account_existing_client(provider):
    """Идемпотентность — клиент уже существует."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[
            {"id": "client_xyz", "name": "123456"}
        ])
    )
    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients/client_xyz/config").mock(
        return_value=httpx.Response(200, text="[Interface]\nPrivateKey = abc...")
    )

    result = await provider.create_account(123456, 30, 0)

    assert result.success is True
    assert result.client_id == "client_xyz"


@pytest.mark.asyncio
@respx.mock
async def test_renew_account_existing(provider):
    """Продление существующего клиента."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[
            {"id": "client_xyz", "name": "123456"}
        ])
    )
    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients/client_xyz/config").mock(
        return_value=httpx.Response(200, text="[Interface]\nPrivateKey = abc...")
    )

    result = await provider.renew_account(123456, 30, 0)

    assert result.success is True
    assert result.client_id == "client_xyz"
    assert result.expiry_days == 30


@pytest.mark.asyncio
@respx.mock
async def test_renew_account_not_found(provider):
    """Продление — клиента нет, создаём нового."""

    # find_client_by_name — нет клиента
    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[])
    )
    # create_account внутри
    respx.post("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json={"id": "client_new", "name": "123456"})
    )
    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients/client_new/config").mock(
        return_value=httpx.Response(200, text="[Interface]\nPrivateKey = abc...")
    )

    result = await provider.renew_account(123456, 30, 0)

    assert result.success is True
    assert result.client_id == "client_new"


@pytest.mark.asyncio
@respx.mock
async def test_delete_account(provider):
    """Удаление клиента."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[
            {"id": "client_xyz", "name": "123456"}
        ])
    )
    respx.delete("http://fake-server:8080/api/servers/wg_abc123/clients/client_xyz").mock(
        return_value=httpx.Response(200, json={"status": "deleted"})
    )

    result = await provider.delete_account(123456)
    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_delete_account_not_found(provider):
    """Идемпотентность — клиента нет, не падаем."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await provider.delete_account(999999)
    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_get_status_found(provider):
    """Статус — клиент существует."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[
            {"id": "client_xyz", "name": "123456"}
        ])
    )

    result = await provider.get_status(123456)
    assert result.success is True
    assert result.is_active is True


@pytest.mark.asyncio
@respx.mock
async def test_get_status_not_found(provider):
    """Статус — клиента нет."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await provider.get_status(999999)
    assert result.success is False


@pytest.mark.asyncio
@respx.mock
async def test_create_account_api_error(provider):
    """API недоступен — возвращаем success=False, не падаем."""

    respx.get("http://fake-server:8080/api/servers/wg_abc123/clients").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    result = await provider.create_account(123456, 30, 0)
    assert result.success is False
    assert result.error is not None
