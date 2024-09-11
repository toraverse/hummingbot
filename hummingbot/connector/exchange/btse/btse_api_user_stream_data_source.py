import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.btse import btse_constants as CONSTANTS
from hummingbot.connector.exchange.btse.btse_auth import BtseAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.btse.btse_exchange import BtseExchange


class BtseAPIUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: BtseAuth,
                 trading_pairs: List[str],
                 connector: 'BtseExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: BtseAuth = auth
        self._domain = domain
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()

        ws_url = f"{CONSTANTS.WSS_URL.format(self._domain)}"
        ws_url = ws_url.replace(".com", ".io") if "testws" in ws_url else ws_url
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

        authentication_payload = self._auth._generate_ws_authentication_payload()
        authenticate_request: WSJSONRequest = WSJSONRequest(payload=authentication_payload)

        await ws.send(authenticate_request)

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the order statuses and trade-fill events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload = {
                "op": "subscribe",
                "args": ["notificationApiV2"],
            }
            subscribe_orders_request: WSJSONRequest = WSJSONRequest(payload=payload)

            payload = {
                "op": "subscribe",
                "args": ["fills"],
            }
            subscribe_trades_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await websocket_assistant.send(subscribe_orders_request)
            await websocket_assistant.send(subscribe_trades_request)

            self.logger().info("Subscribed to private orders and trades channel.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to private orders and trades streams...",
                exc_info=True
            )
            raise

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        await self._sleep(5)
