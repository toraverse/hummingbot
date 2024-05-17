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
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_utils, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange
from hummingbot.connector.exchange.tegro.tegro_utils import get_client_order_id
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent


class TegroExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.chain = ""
        cls.rpc_url = ""
        cls.base_asset = "WETH"
        cls.quote_asset = "USDT"
        cls.market_id = ""
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.tegro_api_key = "somePassPhrase"
        cls.tegro_api_secret = "someSecretKey"

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL, domain=self.exchange._domain)
        url = f"{url.format(self.chain)}?verified=true"
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.exchange._domain)
        url = f"{url.format(self.chain, self.market_id)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        url = f"{url.format(self.chain, self.market_id)}"
        return url

    @property
    def order_creation_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        url = f"{url.format(self.chain, self.tegro_api_key)}"
        return url

    @property
    def all_symbols_request_mock_response(self):
        return {
            "data": [
                {
                    "id": "8453_0x4200000000000000000000000000000000000006_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "base_contract_address": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "chain_id": 8453,
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "verified",
                    "base_symbol": self.base_asset,
                    "quote_symbol": self.quote_asset,
                    "base_decimal": 18,
                    "quote_decimal": 6,
                    "logo": "",
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
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {
            "data": [
                {
                    "id": "",  # noqa: mock
                    "base_contract_address": "",  # noqa: mock
                    "quote_contract_address": "",  # noqa: mock
                    "chain_id": 8453,
                    "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                    "state": "verified",
                    "base_symbol": "INVALID",
                    "quote_symbol": "PAIR",
                    "base_decimal": 18,
                    "quote_decimal": 6,
                    "logo": "",
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
            ],
            "seccess": "false"
        }

        return "INVALID-PAIR", response

    @property
    def latest_prices_request_mock_response(self):
        return {
            "data":
                {
                    "id": "8453_0x4200000000000000000000000000000000000006_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "base_contract_address": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "chain_id": 8453,
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "verified",
                    "base_symbol": self.base_asset,
                    "quote_symbol": self.quote_asset,
                    "base_decimal": 18,
                    "quote_decimal": 6,
                    "logo": "",
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
        },

    @property
    def network_status_request_successful_mock_response(self):
        return {
            "data":
                {
                    "id": "8453_0x4200000000000000000000000000000000000006_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "base_contract_address": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "chain_id": 8453,
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "verified",
                    "base_symbol": self.base_asset,
                    "quote_symbol": self.quote_asset,
                    "base_decimal": 18,
                    "quote_decimal": 6,
                    "logo": "",
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
            "success": True
        }

    @property
    def trading_rules_request_mock_response(self):
        return {
            "data": [
                {
                    "id": "8453_0x4200000000000000000000000000000000000006_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "base_contract_address": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "chain_id": 8453,
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "state": "verified",
                    "base_symbol": self.base_asset,
                    "quote_symbol": self.quote_asset,
                    "base_decimal": 18,
                    "quote_decimal": 6,
                    "logo": "",
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
            ],
            "success": True
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
            "data": {
                "orderId": self.expected_exchange_order_id,
                "originalQuantity": "0.001298701298701299",
                "realOriginalQuantity": "1298701298701299",
                "executedQty": "0.0012987012987013",
                "realExecutedQty": "1298701298701299",
                "status": "Pending",
                "timestamp": "2024-05-16T12:05:03.59076Z"
            }
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
            min_order_size= Decimal(0.0001),
            min_price_increment=Decimal(0.280),
            min_base_amount_increment=Decimal(0.0001)
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
        return "TrID1"

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return TegroExchange(
            client_config_map=client_config_map,
            chain=self.chain,  # noqa: mock
            rpc_url=self.rpc_url,  # noqa: mock
            tegro_api_key=self.tegro_api_key,  # noqa: mock
            tegro_api_secret=self.tegro_api_secret,  # noqa: mock
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
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        response = {
            "data": [
                {
                    "clOrdId": order.client_order_id,
                    "ordId": order.exchange_order_id or "dummyExchangeOrderId",
                    "sCode": "1",
                    "sMsg": "Error"
                }
            ]
        }
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        # Implement the expected not found response when enabling test_cancel_order_not_found_in_the_exchange
        raise NotImplementedError

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
        url = web_utils.public_rest_url(CONSTANTS.TRADES_FOR_ORDER_PATH_URL)
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_LIST)
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_LIST)
        mock_api.get(url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_LIST)
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_PATH_URL.format(self.chain))
        regex_url = f"{url}?market_symbol={self.trading_pair}'"
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL)
        regex_url = f"{url.format(order.exchange_order_id)}"
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        # Implement the expected not found response when enabling
        # test_lost_order_removed_if_not_found_during_order_status_update
        raise NotImplementedError

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL)
        regex_url = f"{url.format(order.exchange_order_id)}"
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL)
        regex_url = f"{url.format(order.exchange_order_id)}"
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "order_placed",
            "data": {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "orderHash": "26c9354ee66ced32f74a3c9ba388f80c155012accd5c1b10589d3a9a0d644b73",  # noqa: mock
                "orderId": order.exchange_order_id,
                "price": str(order.price),
                "pricePrecision": "300000000",
                "quantity": str(order.amount),
                "quantityFilled": 0,
                "quoteCurrency": self.quote_asset,
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "Pending",
                "time": "2024-05-16T12:08:23.199339712Z",
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {}

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
        return {}

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

        url = web_utils.public_rest_url(CONSTANTS.ORDER_LIST)
        regex_url = f"{url.format(self.tegro_api_key)}"

        order_status = {
            "orderId": str(order.exchange_order_id),
            "orderHash": "f27c235af9a19d8539d1a142b000f6370afd8a53a67c4d432504e4e8d7b9bbff",  # noqa: mock
            "marketId": "8453_0x4200000000000000000000000000000000000006_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
            "side": "buy",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 18,
            "quoteDecimals": 6,
            "contractAddress": "0x4200000000000000000000000000000000000006",
            "quantity": 0.001566,
            "quantityFilled": 0.001566,
            "price": 3193.6696,
            "avgPrice": 3193.6696,
            "pricePrecision": "3193669600",
            "volumePrecision": "0",
            "total": 5,
            "fee": 0,
            "status": "Partial",
            "cancel_reason": "",
            "time": "2024-04-30T07:02:36.300856Z"
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
                f" update_timestamp={tegro_utils.datetime_val_or_now(order_status['updateTime'])}, new_state={repr(OrderState.FAILED)}, "
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
            "avgPrice": 0,
            "baseCurrency": self.base_asset,
            "baseDecimals": 18,
            "cancel_reason": "",
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "fee": 0,
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "orderHash": "43afbfb69980fc4cfde15f51ccfd00367603bd24430856b035eb173c622f08f1",  # noqa: mock
            "orderId": str(order.exchange_order_id),
            "price": 3079.999999,
            "pricePrecision": "3079999999",
            "quantity": 0.001299,
            "quantityFilled": 0.001299,
            "quoteCurrency": self.quote_asset,
            "quoteDecimals": 6,
            "side": "buy",
            "status": "Cancelled",
            "time": "2024-05-16T10:57:42.684507Z",
            "total": 4,
            "volumePrecision": "0"
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
                price=Decimal("0.001"),
            ))

    def test_format_trading_rules__min_notional_present(self):
        trading_rules = [
            {
                "data":
                {
                    "id": "8453_0x4200000000000000000000000000000000000006_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "base_contract_address": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "chain_id": 8453,
                    "symbol": "WETH_USDC",
                    "state": "verified",
                    "base_symbol": "WETH",
                    "quote_symbol": "USDC",
                    "base_decimal": 18,
                    "quote_decimal": 6,
                    "logo": "",
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
                "success": True
            },
        ]
        exchange_info = {"data": trading_rules[0]['data']}

        result = self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info))

        self.assertEqual(result[0].min_notional_size, Decimal("0.0001"))

    def test_format_trading_rules__notional_but_no_min_notional_present(self):
        trading_rules = [
            {
                "data":
                {
                    "id": "8453_0x4200000000000000000000000000000000000006_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "base_contract_address": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "chain_id": 8453,
                    "symbol": "WETH_USDC",
                    "state": "verified",
                    "base_symbol": "WETH",
                    "quote_symbol": "USDC",
                    "base_decimal": 18,
                    "quote_decimal": 6,
                    "logo": "",
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
                "success": True
            }
        ]
        exchange_info = {"data": trading_rules[0]['data']}

        result = self.async_run_with_timeout(self.exchange._format_trading_rules(exchange_info[0]['data']))

        self.assertEqual(result.min_notional_size, Decimal("0.0001"))

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
            "avgPrice": 0,
            "baseCurrency": self.base_asset,
            "baseDecimals": 18,
            "cancel_reason": "",
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "fee": 0,
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "orderHash": "43afbfb69980fc4cfde15f51ccfd00367603bd24430856b035eb173c622f08f1",  # noqa: mock
            "orderId": str(order.exchange_order_id),
            "price": str(order.price),
            "pricePrecision": "3079999999",
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "quoteCurrency": self.quote_asset,
            "quoteDecimals": 6,
            "side": order.order_type.name.lower(),
            "status": "Active",
            "time": "2024-05-16T10:57:42.684507Z",
            "total": 4,
            "volumePrecision": "0"
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "avgPrice": 0,
            "baseCurrency": self.base_asset,
            "baseDecimals": 18,
            "cancel_reason": "",
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "fee": 0,
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "orderHash": "43afbfb69980fc4cfde15f51ccfd00367603bd24430856b035eb173c622f08f1",  # noqa: mock
            "orderId": str(order.exchange_order_id),
            "price": str(order.price),
            "pricePrecision": "3079999999",
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "quoteCurrency": self.quote_asset,
            "quoteDecimals": 6,
            "side": order.order_type.name.lower(),
            "status": "Cancelled",
            "time": "2024-05-16T10:57:42.684507Z",
            "total": 4,
            "volumePrecision": "0"
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "avgPrice": 0,
            "baseCurrency": self.base_asset,
            "baseDecimals": 18,
            "cancel_reason": "",
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "fee": 0,
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "orderHash": "43afbfb69980fc4cfde15f51ccfd00367603bd24430856b035eb173c622f08f1",  # noqa: mock
            "orderId": str(order.exchange_order_id),
            "price": str(order.price),
            "pricePrecision": "3079999999",
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "quoteCurrency": self.quote_asset,
            "quoteDecimals": 6,
            "side": order.order_type.name.lower(),
            "status": "Active",
            "time": "2024-05-16T10:57:42.684507Z",
            "total": 4,
            "volumePrecision": "0"
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "avgPrice": 0,
            "baseCurrency": self.base_asset,
            "baseDecimals": 18,
            "cancel_reason": "",
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "fee": 0,
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "orderHash": "43afbfb69980fc4cfde15f51ccfd00367603bd24430856b035eb173c622f08f1",  # noqa: mock
            "orderId": str(order.exchange_order_id),
            "price": str(order.price),
            "pricePrecision": "3079999999",
            "quantity": str(order.amount),
            "quantityFilled": str(order.amount),
            "quoteCurrency": self.quote_asset,
            "quoteDecimals": 6,
            "side": order.order_type.name.lower(),
            "status": "Pending",
            "time": "2024-05-16T10:57:42.684507Z",
            "total": 4,
            "volumePrecision": "0"
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "orderHash": "43afbfb69980fc4cfde15f51ccfd00367603bd24430856b035eb173c622f08f1",  # noqa: mock
                "orderId": str(order.exchange_order_id),
                "price": str(order.price),
                "pricePrecision": "3079999999",
                "quantity": str(order.amount),
                "quantityFilled": str(order.amount),
                "quoteCurrency": self.quote_asset,
                "quoteDecimals": 6,
                "side": order.order_type.name.lower(),
                "status": "Pending",
                "time": "2024-05-16T10:57:42.684507Z",
                "total": 4,
                "volumePrecision": "0"
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "orderHash": "43afbfb69980fc4cfde15f51ccfd00367603bd24430856b035eb173c622f08f1",  # noqa: mock
                "orderId": str(order.exchange_order_id),
                "price": str(order.price),
                "pricePrecision": "3079999999",
                "quantity": str(order.amount),
                "quantityFilled": str(order.amount),
                "quoteCurrency": self.quote_asset,
                "quoteDecimals": 6,
                "side": order.order_type.name.lower(),
                "status": "Matched",
                "time": "2024-05-16T10:57:42.684507Z",
                "total": 4,
                "volumePrecision": "0"
            }
        ]
