import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from web3 import HTTPProvider, Web3

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils
from hummingbot.connector.exchange.tegro.tegro_auth import TegroAuth
from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class TegroDexClient:
    signed_order_types = {}

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 tegro_api_key: str,
                 wallet_private_key: str,
                 api_factory: WebAssistantsFactory,
                 trading_pairs: Optional[List[str]] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        self._connector = TegroExchange
        self._provider_url = CONSTANTS.TEGRO_BASE_URL
        self.provider = Web3(HTTPProvider(self._provider_url))
        self._client_config_map = client_config_map
        self._api_key = tegro_api_key
        self._api_secret = wallet_private_key
        self._time_synchronizer = time_synchronizer
        self._domain: Optional[str] = CONSTANTS.DOMAIN
        self._trading_pairs = trading_pairs
        self._api_factory = api_factory

    @property
    async def _generate_typed_data(self):
        data = await self.generate_typed_data()
        return data

    @staticmethod
    def provider_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
        base_url = CONSTANTS.TEGRO_BASE_URL if domain == "tegro" else CONSTANTS.TESTNET_BASE_URL
        return base_url + path_url

    @property
    def authenticator(self):
        return TegroAuth(
            api_key=self._api_key,
            api_secret=self._api_secret)

    @staticmethod
    def public_rest_url(path_url: str, domain: str = "tegro"):
        base_url = CONSTANTS.TEGRO_BASE_URL if domain == "tegro" else CONSTANTS.TESTNET_BASE_URL
        return base_url + path_url

    async def generate_typed_data(self, amount: str, order_type: OrderType, price: Decimal, trade_type: TradeType,) -> Dict[str, Any]:
        trading_pairs = self._trading_pairs
        amount_str = f"{amount}"
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        params = {
            "market_symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pairs),
            "chain_id": CONSTANTS.CHAIN_ID,
            "wallet_address": self._api_key,
            "side": side_str,
            "amount": amount_str,
        }
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            price_str = f"{price:f}"
            params["price"] = price_str
        rest_assistant = await self._api_factory.get_rest_assistant()
        data_resp = await rest_assistant.execute_request(
            url=tegro_web_utils.public_rest_url(path_url=CONSTANTS.GENERATE_SIGN_URL, domain=self._domain),
            params=params,
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.GENERATE_SIGN_URL,
        )
        return data_resp

    async def create_order(self, amount: str, trade_type, price, order_type):
        transaction_data = await self.generate_typed_data(amount, order_type, price, trade_type)
        # Convert the message to bytes
        message = json.dumps({
            **transaction_data["data"]["sign_data"]["domain"],
            **{"Order": transaction_data["data"]["sign_data"]["types"]["Order"]},
            **json.loads(transaction_data["data"]["limit_order"]["raw_order_data"])
        }).encode("utf-8")

        # Sign the message using the private key
        signature = await self.provider.eth.account.sign_message(message, self._api_secret)
        body = {
            **transaction_data["data"]["limit_order"],
            "signature": signature
        }
        request_body = await self.provider.eth.account.sign_transaction(body, self._api_secret)
        return request_body, transaction_data
