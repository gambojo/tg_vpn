# services/vpn_service.py

from config import settings
from services.vpn_base import BaseVpnProvider


def get_vpn_provider() -> BaseVpnProvider:
    if settings.VPN_PROVIDER == "xui":
        from services.vpn_xui import XuiVpnProvider
        return XuiVpnProvider(
            panel_url=settings.XUI_PANEL_URL,
            username=settings.XUI_USERNAME,
            password=settings.XUI_PASSWORD,
            external_ip=settings.XUI_EXTERNAL_IP,
            server_port=settings.XUI_SERVER_PORT,
            inbound_id=settings.XUI_INBOUND_ID,
            server_name=settings.XUI_SERVER_NAME,
        )
    elif settings.VPN_PROVIDER == "amnezia":
        from services.vpn_amnezia import AmneziaVpnProvider
        return AmneziaVpnProvider(
            api_url=settings.AWG_API_URL,
            server_id=settings.AWG_SERVER_ID,
            username=settings.AWG_USERNAME,
            password=settings.AWG_PASSWORD,
        )
    else:
        raise ValueError(f"Unknown VPN_PROVIDER: {settings.VPN_PROVIDER}")

# Глобальный экземпляр — handler'ы импортируют только это
vpn: BaseVpnProvider = get_vpn_provider()
