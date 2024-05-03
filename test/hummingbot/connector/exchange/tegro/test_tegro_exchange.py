import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange
from hummingbot.connector.exchange.tegro.tegro_utils import get_client_order_id
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent


class TegroExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @property
    def all_symbols_url(self):
        return web_utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL, domain=self.exchange._domain)
        return url

    @property
    def network_status_url(self):
        url = web_utils.rest_url(CONSTANTS.CHAIN_LIST, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "data": [
                {
                    "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                    "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "chainId": 80001,
                    "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "verified",
                    "BaseSymbol": self.base_asset,
                    "QuoteSymbol": self.quote_asset,
                    "BaseDecimal": 4,
                    "QuoteDecimal": 4,
                    "CreatedAt": "2024-01-08T16:36:40.365473Z",
                    "UpdatedAt": "2024-01-08T16:36:40.365473Z",
                    "ticker": {
                        "base_volume": 265306,
                        "quote_volume": 1423455.3812000754,
                        "price": 0.9541,
                        "price_change_24h": -85.61,
                        "price_high_24h": 10,
                        "price_low_24h": 0.2806,
                        "ask_low": 0.2806,
                        "bid_high": 10
                    }
                },
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "chainId": 80001,
            "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "state": "verified",
            "BaseSymbol": self.base_asset,
            "QuoteSymbol": self.quote_asset,
            "BaseDecimal": 4,
            "QuoteDecimal": 4,
            "CreatedAt": "2024-01-08T16:36:40.365473Z",
            "UpdatedAt": "2024-01-08T16:36:40.365473Z",
            "ticker": {
                "base_volume": 265306,
                "quote_volume": 1423455.3812000754,
                "price": str(self.expected_latest_price),
                "price_change_24h": -85.61,
                "price_high_24h": 10,
                "price_low_24h": 0.2806,
                "ask_low": 0.2806,
                "bid_high": 10
            }
        },

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "data": [
                {
                    "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                    "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "chainId": 80001,
                    "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "verified",
                    "BaseSymbol": self.base_asset,
                    "QuoteSymbol": self.quote_asset,
                    "BaseDecimal": 4,
                    "QuoteDecimal": 4,
                    "CreatedAt": "2024-01-08T16:36:40.365473Z",
                    "UpdatedAt": "2024-01-08T16:36:40.365473Z",
                    "ticker": {
                        "base_volume": 265306,
                        "quote_volume": 1423455.3812000754,
                        "price": 0.9541,
                        "price_change_24h": -85.61,
                        "price_high_24h": 10,
                        "price_low_24h": 0.2806,
                        "ask_low": 0.2806,
                        "bid_high": 10
                    }
                },
                {
                    "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                    "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "chainId": 80001,
                    "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "state": "verified",
                    "BaseSymbol": self.base_asset,
                    "QuoteSymbol": self.quote_asset,
                    "BaseDecimal": 4,
                    "QuoteDecimal": 4,
                    "CreatedAt": "2024-01-08T16:36:40.365473Z",
                    "UpdatedAt": "2024-01-08T16:36:40.365473Z",
                    "ticker": {
                        "base_volume": 265306,
                        "quote_volume": 1423455.3812000754,
                        "price": 0.9541,
                        "price_change_24h": -85.61,
                        "price_high_24h": 10,
                        "price_low_24h": 0.2806,
                        "ask_low": 0.2806,
                        "bid_high": 10
                    }
                }
            ]

        }

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "chainId": 80001,
            "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
            "state": "verified",
            "BaseSymbol": self.base_asset,
            "QuoteSymbol": self.quote_asset,
            "BaseDecimal": 4,
            "QuoteDecimal": 4,
            "CreatedAt": "2024-01-08T16:36:40.365473Z",
            "UpdatedAt": "2024-01-08T16:36:40.365473Z",
            "ticker": {
                "base_volume": 265306,
                "quote_volume": 1423455.3812000754,
                "price": 0.9541,
                "price_change_24h": -85.61,
                "price_high_24h": 10,
                "price_low_24h": 0.2806,
                "ask_low": 0.2806,
                "bid_high": 10
            }
        }

    @property
    def trading_rules_request_mock_response(self):
        return {
            "data": [
                {
                    "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                    "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "chainId": 80001,
                    "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "verified",
                    "BaseSymbol": self.base_asset,
                    "QuoteSymbol": self.quote_asset,
                    "BaseDecimal": 4,
                    "QuoteDecimal": 4,
                    "CreatedAt": "2024-01-08T16:36:40.365473Z",
                    "UpdatedAt": "2024-01-08T16:36:40.365473Z",
                    "ticker": {
                        "base_volume": 265306,
                        "quote_volume": 1423455.3812000754,
                        "price": 0.9541,
                        "price_change_24h": -85.61,
                        "price_high_24h": 10,
                        "price_low_24h": 0.2806,
                        "ask_low": 0.2806,
                        "bid_high": 10
                    }
                },
            ]
        }

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "chainId": 80001,
            "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "state": "verified",
            "BaseSymbol": self.base_asset,
            "QuoteSymbol": self.quote_asset,
            "BaseDecimal": 4,
            "QuoteDecimal": 4,
            "CreatedAt": "2024-01-08T16:36:40.365473Z",
            "UpdatedAt": "2024-01-08T16:36:40.365473Z",
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "orderId": self.expected_exchange_order_id,
            "originalQuantity": "1",
            "realOriginalQuantity": "10000",
            "executedQty": "1",
            "realExecutedQty": "10000",
            "status": "Pending",
            "timestamp": "2024-04-06T14:54:57.089199Z"
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "data": [
                {
                    "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "balance": 10000,
                    "symbol": self.base_asset,
                    "decimal": 4,
                    "price": 0,
                    "price_change_24_h": 0,
                    "type": "quote",
                    "placed_amount": 22
                },
                {
                    "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "balance": 10000,
                    "symbol": self.quote_asset,
                    "decimal": 4,
                    "price": 0,
                    "price_change_24_h": 0,
                    "type": "quote",
                    "placed_amount": 22
                },
            ],
            "success": True
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "data": [
                {
                    "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "balance": 10000,
                    "symbol": self.base_asset,
                    "decimal": 4,
                    "price": 0,
                    "price_change_24_h": 0,
                    "type": "quote",
                    "placed_amount": 22
                },
            ],
            "success": True
        }

    @property
    def balance_event_websocket_update(self):
        return {}

    @property
    def expected_latest_price(self):
        return 0.9541

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size= Decimal(0.1),
            min_price_increment=Decimal(0.280),
            min_base_amount_increment=Decimal(1)
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["data"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "a60fe011-a79d-47ca-b7b3-041d52b087f3"  # noqa: mock

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return ""

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return TegroExchange(
            client_config_map=client_config_map,
            chain="polygon",  # noqa: mock
            tegro_api_key="testAPIKey",  # noqa: mock
            tegro_api_secret="testSecret",  # noqa: mock
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["symbol"])
        self.assertEqual(order.trade_type.name.upper(), request_data["side"])
        # self.assertEqual(TegroExchange.tegro_order_type(OrderType.LIMIT), request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["orderId"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["params"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_data["symbol"])
        self.assertEqual(order.client_order_id, request_data["orderId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["orderId"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                         request_params["symbol"])
        self.assertEqual(order.exchange_order_id, str(request_params["orderId"]))

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2011, "msg": "Unknown order sent."}
        mock_api.post(regex_url, status=400, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_PATH_URL.format(80001))
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2013, "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_PATH_URL.format(self.api_key))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_PATH_URL.format(80001))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "baseCurrency": self.base_asset,
            "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "orderHash": "8ab2654689da67008beee1101d86bf4edcfc084327bab9e93472bbd0424cab34",  # noqa: mock
            "orderId": order.exchange_order_id,
            "price": str(order.price),
            "quantity": str(order.amount),
            "quantityFilled": str(Decimal("0")),
            "quoteCurrency": self.quote_asset,
            "side": order.trade_type.name.lower(),
            "status": "Pending",
            "time": "2024-04-06T14:54:57.0891994Z"
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "baseCurrency": self.base_asset,
            "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "orderHash": "8ab2654689da67008beee1101d86bf4edcfc084327bab9e93472bbd0424cab34",  # noqa: mock
            "orderId": "dummyText",
            "price": str(order.price),
            "quantity": str(order.amount),
            "quantityFilled": str(Decimal("0")),
            "quoteCurrency": self.quote_asset,
            "side": order.trade_type.name.lower(),
            "status": "Cancelled",
            "time": "2024-04-06T14:54:57.0891994Z"
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "baseCurrency": self.base_asset,
            "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "orderHash": "8ab2654689da67008beee1101d86bf4edcfc084327bab9e93472bbd0424cab34",  # noqa: mock
            "orderId": order.exchange_order_id,
            "price": str(order.price),
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "quoteCurrency": self.quote_asset,
            "side": order.trade_type.name.lower(),
            "status": "Matched",
            "time": "2024-04-06T14:54:57.0891994Z"
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "baseCurrency": self.base_asset,
            "contractAddress": "0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba",  # noqa: mock
            "orderHash": "6ad6f31037d95683382eb1c44410a12dc392962e20729294817c22439ca67b8f",  # noqa: mock
            "orderId": str(order.exchange_order_id),
            "price": 10000,
            "quantity": 1,
            "quantityFilled": 1,
            "quoteCurrency": self.quote_asset,
            "side": "buy",
            "status": "Cancelled",
            "time": "2024-04-11T20:36:53.763276Z"
        }
        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        request = self._all_executed_requests(mock_api, url)[0]
        self.validate_auth_credentials_present(request)
        request_params = request.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), f'{request_params["baseCurrency"]}_{request_params["quoteCurrency"]}')

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={order_status['updateTime'] * 1e-3}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
                "misc_updates=None)")
        )

    def test_user_stream_update_for_order_failure(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "baseCurrency": self.base_asset,
            "contractAddress": "0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba",  # noqa: mock
            "orderHash": "6ad6f31037d95683382eb1c44410a12dc392962e20729294817c22439ca67b8f",  # noqa: mock
            "orderId": str(order.exchange_order_id),
            "price": 1000,
            "quantity": 1,
            "quantityFilled": 1,
            "quoteCurrency": self.quote_asset,
            "side": "buy",
            "status": "Matched",
            "time": "2024-04-11T20:36:53.763276Z"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_failure)
        self.assertTrue(order.is_done)

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 7

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_client_order_id(
            is_buy=True,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_client_order_id(
            is_buy=False,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_time_synchronizer_related_request_error_detection(self):
        exception = IOError("Error executing request POST https://api.testnet.tegro.com/v2/chain/list HTTP status is 400. "
                            "Error: {'code':-1021,'msg':'Timestamp for this request is outside of the recvWindow.'}")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.testnet.tegro.com/v2/chain/list HTTP status is 400. "
                            "Error: {'code':-1021,'msg':'Timestamp for this request was 1000ms ahead of the server's "
                            "time.'}")
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.testnet.tegro.com/v2/chain/list HTTP status is 400. "
                            "Error: {'code':-1022,'msg':'Timestamp for this request was 1000ms ahead of the server's "
                            "time.'}")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

        exception = IOError("Error executing request POST https://api.testnet.tegro.com/v2/chain/list HTTP status is 400. "
                            "Error: {'code':-1021,'msg':'Other error.'}")
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(exception))

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_unkown_order(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Unknown error, please check your request or try again later."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        o_id, transact_time = self.async_run_with_timeout(self.exchange._place_order(
            order_id="test_order_id",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        ))
        self.assertEqual(o_id, "UNKNOWN")

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_failure(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Service Unavailable."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="test_order_id",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

        mock_response = {"code": -1003, "msg": "Internal error; unable to process your request. Please try again."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="test_order_id",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

    def test_format_trading_rules__min_notional_present(self):
        trading_rules = [
            {
                "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "chainId": 80001,
                "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "symbol": "COINALPHA_HBOT",
                "state": "verified",
                "BaseSymbol": "COINALPHA",
                "QuoteSymbol": "HBOT",
                "BaseDecimal": 4,
                "QuoteDecimal": 4,
                "CreatedAt": "2024-01-08T16:36:40.365473Z",
                "UpdatedAt": "2024-01-08T16:36:40.365473Z",
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
        ]
        exchange_info = {"data": trading_rules}

        result = self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        self.assertEqual(result[0].min_notional_size, Decimal("0.00100000"))

    def test_format_trading_rules__notional_but_no_min_notional_present(self):
        trading_rules = [
            {
                "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "chainId": 80001,
                "id": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "symbol": "COINALPHA_HBOT",
                "state": "verified",
                "BaseSymbol": "COINALPHA",
                "QuoteSymbol": "HBOT",
                "BaseDecimal": 4,
                "QuoteDecimal": 4,
                "CreatedAt": "2024-01-08T16:36:40.365473Z",
                "UpdatedAt": "2024-01-08T16:36:40.365473Z",
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
        ]
        exchange_info = {"data": trading_rules}

        result = self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        self.assertEqual(result[0].min_notional_size, Decimal("10"))

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        self.assertIn("signature", params)
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("X-MBX-APIKEY", request_headers)

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "Order Cancel request is successful."
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": order.exchange_order_id,
            "orderHash": "6f3b34767f9939a29cd85a83878baddb89387289df27a9a95daf6dc6405abed5",  # noqa: mock
            "marketId": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "side": order.order_type.name.lower(),
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 4,
            "quoteDecimals": 4,
            "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "price": str(order.price),
            "status": "Active",
            "time": "2024-04-11T19:55:52.764151Z"
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": order.exchange_order_id,
            "orderHash": "6f3b34767f9939a29cd85a83878baddb89387289df27a9a95daf6dc6405abed5",  # noqa: mock
            "marketId": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "side": order.order_type.name.lower(),
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 4,
            "quoteDecimals": 4,
            "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "price": str(order.price),
            "status": "Cancelled",
            "time": "2024-04-11T19:55:52.764151Z"
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": order.exchange_order_id,
            "orderHash": "6f3b34767f9939a29cd85a83878baddb89387289df27a9a95daf6dc6405abed5",  # noqa: mock
            "marketId": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "side": order.order_type.name.lower(),
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 4,
            "quoteDecimals": 4,
            "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "price": str(order.price),
            "status": "Active",
            "time": "2024-04-11T19:55:52.764151Z"
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "orderId": str(order.exchange_order_id),
            "orderHash": "6f3b34767f9939a29cd85a83878baddb89387289df27a9a95daf6dc6405abed5",  # noqa: mock
            "marketId": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
            "side": order.order_type.name.lower(),
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 4,
            "quoteDecimals": 4,
            "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "price": str(order.price),
            "status": "Pending",
            "time": "2024-04-11T19:55:52.764151Z"
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "orderId": str(order.exchange_order_id),
                "orderHash": "6f3b34767f9939a29cd85a83878baddb89387289df27a9a95daf6dc6405abed5",  # noqa: mock
                "marketId": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "side": order.order_type.name.lower(),
                "baseCurrency": self.base_asset,
                "quoteCurrency": self.quote_asset,
                "baseDecimals": 4,
                "quoteDecimals": 4,
                "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                "quantity": str(order.amount),
                "quantityFilled": str(order.amount),
                "price": str(order.price),
                "status": "Pending",
                "time": "2024-04-11T19:55:52.764151Z"
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "orderId": str(order.exchange_order_id),
                "orderHash": "6f3b34767f9939a29cd85a83878baddb89387289df27a9a95daf6dc6405abed5",  # noqa: mock
                "marketId": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "side": order.order_type.name.lower(),
                "baseCurrency": self.base_asset,
                "quoteCurrency": self.quote_asset,
                "baseDecimals": 4,
                "quoteDecimals": 4,
                "contractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                "quantity": str(order.amount),
                "quantityFilled": str(order.amount),
                "price": str(order.price),
                "status": "Active",
                "time": "2024-04-11T19:55:52.764151Z"
            }
        ]
