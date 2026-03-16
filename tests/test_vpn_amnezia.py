import os
os.environ["BOT_TOKEN"] = "123456:test"
os.environ["VPN_PROVIDER"] = "amnezia"
os.environ["AWG_API_URL"] = "http://fake-server:8080"
os.environ["AWG_SERVER_ID"] = "wg_abc123"
os.environ["AWG_USERNAME"] = "admin"
os.environ["AWG_PASSWORD"] = "password"

import pytest
import respx
import httpx
from services.vpn_amnezia import AmneziaVpnProvider

# ------------------------------------------------------------------
# Реальные данные из API (взяты с боевого сервера)
# ------------------------------------------------------------------
SERVER_ID = "f9f0d8"
CLIENT_ID = "b3e2b6"
CLIENT_NAME = "785818468"

REAL_CLIENT = {
    "id": CLIENT_ID,
    "name": CLIENT_NAME,
    "status": "active",
    "client_ip": "10.0.0.2",
    "server_id": SERVER_ID,
    "server_name": "AmneziaWG VPN",
    "obfuscation_enabled": True,
    "obfuscation_params": {"Jc": 8, "Jmin": 8, "Jmax": 80, "S1": 50, "S2": 60,
                           "H1": 1000, "H2": 2000, "H3": 3000, "H4": 4000, "MTU": 1280},
}

REAL_CONFIG = (
    "# AmneziaWG Client Configuration\n"
    "# Server: AmneziaWG VPN\n"
    f"# Client: {CLIENT_NAME}\n"
    "[Interface]\n"
    "PrivateKey = 2Aoh3jvLCficat40caGNrCuZAKbcJ6wKtNHgeYISD0M=\n"
    "Address = 10.0.0.2/32\n"
    "DNS = 8.8.8.8, 1.1.1.1\n"
    "MTU = 1280\n"
    "Jc = 8\nJmin = 8\nJmax = 80\nS1 = 50\nS2 = 60\n"
    "H1 = 1000\nH2 = 2000\nH3 = 3000\nH4 = 4000\n"
    "[Peer]\n"
    "PublicKey = xAXJBUA8/FwP0YP0KY397DZebIJ+RK6IuG4hfdNKlDU=\n"
    "Endpoint = 94.156.177.212:51820\n"
    "AllowedIPs = 0.0.0.0/0\n"
    "PersistentKeepalive = 25\n"
)

REAL_ADD_RESPONSE = {
    "client": {
        "id": "new_abc1",
        "name": "999999999",
        "status": "active",
        "client_ip": "10.0.0.4",
        "server_id": SERVER_ID,
        "server_name": "AmneziaWG VPN",
        "obfuscation_enabled": True,
        "obfuscation_params": {"Jc": 8, "Jmin": 8, "Jmax": 80, "S1": 50, "S2": 60,
                               "H1": 1000, "H2": 2000, "H3": 3000, "H4": 4000, "MTU": 1280},
    },
    "config": (
        "# AmneziaWG Client Configuration\n"
        "[Interface]\n"
        "PrivateKey = newkey==\n"
        "Address = 10.0.0.4/32\n"
        "DNS = 8.8.8.8, 1.1.1.1\n"
        "[Peer]\n"
        "PublicKey = xAXJBUA8/FwP0YP0KY397DZebIJ+RK6IuG4hfdNKlDU=\n"
        "Endpoint = 94.156.177.212:51820\n"
        "AllowedIPs = 0.0.0.0/0\n"
    ),
}

REAL_SYSTEM_STATUS = {
    "active_servers": 1,
    "awg_available": True,
    "public_ip": "94.156.177.212",
    "total_clients": 2,
    "total_servers": 1,
}

BASE = "http://fake-server:8080"
CLIENTS_URL = f"{BASE}/api/servers/{SERVER_ID}/clients"
CLIENT_CONFIG_URL = f"{BASE}/api/servers/{SERVER_ID}/clients/{CLIENT_ID}/config"
NEW_CLIENT_CONFIG_URL = f"{BASE}/api/servers/{SERVER_ID}/clients/new_abc1/config"
DELETE_URL = f"{BASE}/api/servers/{SERVER_ID}/clients/{CLIENT_ID}"
STATUS_URL = f"{BASE}/api/system/status"


@pytest.fixture
def provider():
    return AmneziaVpnProvider(
        api_url=BASE,
        server_id=SERVER_ID,
        username="admin",
        password="password",
    )


# ------------------------------------------------------------------
# health
# ------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_health_ok(provider):
    """health() возвращает True когда API отвечает."""
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, json=REAL_SYSTEM_STATUS))
    result = await provider.api.health()
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_health_fail(provider):
    """health() возвращает False когда API недоступен."""
    respx.get(STATUS_URL).mock(side_effect=httpx.ConnectError("refused"))
    result = await provider.api.health()
    assert result is False


# ------------------------------------------------------------------
# create_account
# ------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_create_account_new_client(provider):
    """Создание нового клиента — клиента не было."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.post(CLIENTS_URL).mock(return_value=httpx.Response(200, json=REAL_ADD_RESPONSE))

    result = await provider.create_account(
        telegram_id=999999999,
        expiry_days=30,
        data_limit_gb=0,
    )

    assert result.success is True
    assert result.client_id == "new_abc1"
    assert "[Interface]" in result.connection_string
    assert result.expiry_days == 30
    assert result.expiry_time > 0
    assert result.qrcode_buffer is not None


@pytest.mark.asyncio
@respx.mock
async def test_create_account_existing_client(provider):
    """Идемпотентность — клиент уже существует, возвращаем его конфиг."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[REAL_CLIENT]))
    respx.get(CLIENT_CONFIG_URL).mock(return_value=httpx.Response(200, text=REAL_CONFIG))

    result = await provider.create_account(
        telegram_id=int(CLIENT_NAME),
        expiry_days=30,
        data_limit_gb=0,
    )

    assert result.success is True
    assert result.client_id == CLIENT_ID
    assert "PrivateKey" in result.connection_string
    assert "[Interface]" in result.connection_string


@pytest.mark.asyncio
@respx.mock
async def test_create_account_trial(provider):
    """Создание триального аккаунта — is_trial проставляется."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.post(CLIENTS_URL).mock(return_value=httpx.Response(200, json=REAL_ADD_RESPONSE))

    result = await provider.create_account(999999999, expiry_days=3, data_limit_gb=0, is_trial=True)

    assert result.success is True
    assert result.is_trial is True
    assert result.expiry_days == 3


@pytest.mark.asyncio
@respx.mock
async def test_create_account_api_error(provider):
    """API недоступен — возвращаем success=False, не падаем."""
    respx.get(CLIENTS_URL).mock(side_effect=httpx.ConnectError("Connection refused"))

    result = await provider.create_account(123456, 30, 0)

    assert result.success is False
    assert result.error is not None


# ------------------------------------------------------------------
# renew_account
# ------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_renew_account_existing(provider):
    """Продление — клиент есть, конфиг не меняется, expiry обновляется."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[REAL_CLIENT]))
    respx.get(CLIENT_CONFIG_URL).mock(return_value=httpx.Response(200, text=REAL_CONFIG))

    result = await provider.renew_account(int(CLIENT_NAME), expiry_days=30, data_limit_gb=0)

    assert result.success is True
    assert result.client_id == CLIENT_ID
    assert result.expiry_days == 30
    assert "[Interface]" in result.connection_string


@pytest.mark.asyncio
@respx.mock
async def test_renew_account_not_found(provider):
    """Продление — клиента нет, создаём нового."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.post(CLIENTS_URL).mock(return_value=httpx.Response(200, json=REAL_ADD_RESPONSE))

    result = await provider.renew_account(999999999, expiry_days=30, data_limit_gb=0)

    assert result.success is True
    assert result.client_id == "new_abc1"


# ------------------------------------------------------------------
# get_status
# ------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_get_status_active(provider):
    """Статус активного клиента."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[REAL_CLIENT]))

    result = await provider.get_status(int(CLIENT_NAME))

    assert result.success is True
    assert result.client_id == CLIENT_ID
    assert result.is_active is True


@pytest.mark.asyncio
@respx.mock
async def test_get_status_not_found(provider):
    """Статус — клиента нет."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[]))

    result = await provider.get_status(999999999)

    assert result.success is False
    assert result.error == "Клиент не найден"


# ------------------------------------------------------------------
# delete_account
# ------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_delete_account(provider):
    """Удаление клиента — API возвращает {"client_id": "...", "status": "deleted"}."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[REAL_CLIENT]))
    respx.delete(DELETE_URL).mock(
        return_value=httpx.Response(200, json={"client_id": CLIENT_ID, "status": "deleted"})
    )

    result = await provider.delete_account(int(CLIENT_NAME))

    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_delete_account_not_found(provider):
    """Идемпотентность — клиента нет, не падаем."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[]))

    result = await provider.delete_account(999999999)

    assert result.success is True


@pytest.mark.asyncio
@respx.mock
async def test_delete_account_api_error(provider):
    """API падает при удалении — возвращаем success=False."""
    respx.get(CLIENTS_URL).mock(return_value=httpx.Response(200, json=[REAL_CLIENT]))
    respx.delete(DELETE_URL).mock(side_effect=httpx.ConnectError("refused"))

    result = await provider.delete_account(int(CLIENT_NAME))

    assert result.success is False
    assert result.error is not None
