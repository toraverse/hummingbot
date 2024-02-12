import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from web3 import Web3

from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_utils
from hummingbot.connector.exchange.tegro.tegro_auth import TegroAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.connector.exchange.tegro.tegro_exchange import ClientConfigAdapter


class TegroDexClient:
    signed_order_types = {}

    """
    Constructor for TegroDexClient.
    Args:
        base_api_url (str): The base URL of the Tegro DEX API.
        provider_url (str): The URL of the JSON RPC provider.
        wallet_private_key (str): The private key of the user's wallet.
    """

    def __init__(self, client_config_map: "ClientConfigAdapter",
                 base_api_url: str,
                 provider_url: str,
                 tegro_api_key: str,
                 signed: str,
                 wallet_private_key: str,
                 api_factory: WebAssistantsFactory,
                 trading_pairs: Optional[List[str]] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None,
                 domain: Optional[str] = None):
        super().__init__(trading_pairs)
        self.public_rest_url = base_api_url
        self._provider_url = provider_url
        self.provider = Web3.HTTPProvider(provider_url)
        self.web3 = Web3(self.provider)
        self._wallet = signed
        self._client_config_map = client_config_map
        self._api_key = tegro_api_key
        self._api_secret = wallet_private_key
        self._time_synchronizer = time_synchronizer
        self._domain: Optional[str] = domain
        self._trading_pairs = trading_pairs
        self._api_factory = api_factory

    @property
    async def wallet(self, data):
        sign = self.web3.eth.account.sign_transaction(data, self._api_secret),
        return sign

    @property
    async def _signed_order_types(self):
        return self.signed_order_types

    @property
    def provider_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
        return CONSTANTS.TEGRO_BASE_URL[domain] + path_url

    @property
    def authenticator(self):
        return TegroAuth(
            api_key=self._api_key,
            api_secret=self._api_secret)

    @property
    def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
        return CONSTANTS.TEGRO_BASE_URL[domain] + path_url

    async def sign_order_type(self, amount: str, order_type: OrderType, price: Decimal, trade_type: TradeType,) -> Dict[str, Any]:
        trading_pairs = self._trading_pairs
        amount_str = f"{amount:f}"
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
            url=tegro_utils.rest_api_url(path_url=CONSTANTS.GENERATE_SIGN_URL, domain=self._domain),
            params=params,
            method=RESTMethod.POST,
            throttler_limit_id=CONSTANTS.GENERATE_SIGN_URL,
        )

        return data_resp

    async def sign_order(self) -> Dict[str, Any]:
        data_resp = self.signed_order_types
        signature = self.web3.eth.sign_transaction(
            data_resp['data']['sign_data']['domain'],
            {'Order': data_resp['data']['sign_data']['types']['Order']},
            json.loads(data_resp['data']['limit_order']['raw_order_data'])
        )

        data = {
            **data_resp['data']['limit_order'],
            'signature': signature
        }
        request_body = await self.web3.eth.account.sign_transaction(data, self._api_secret)
        return request_body
