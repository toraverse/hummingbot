import asyncio
import json
import re
import time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import MarketOrderFailureEvent, OrderFilledEvent


class TegroExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tegro_api_key = "somePassPhrase"  # noqa: mock
        cls.tegro_api_secret = "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=="  # noqa: mock
        cls.base_asset = "WETH"
        cls.quote_asset = "USDT"  # linear
        cls.chain_id = "polygon"
        cls.domain = "tegro_optimism_testnet"  # noqa: mock
        cls.chain = 80002
        cls.rpc_url = "http://mock-rpc-url"  # noqa: mock
        cls.market_id = "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b"  # noqa: mock

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.exchange._domain)
        url = f"{url}?symbol={self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset)}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def all_symbols_request_mock_response(self):
        mock_response = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
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
        return mock_response

    @property
    def latest_prices_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> list[Dict[str, Any]]:
        response = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
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
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                "state": "verified",
                "base_symbol": "INVALID",
                "quote_symbol": "PAIR",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
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
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "timezone": "UTC",
            "serverTime": 1565246363776,
            "rateLimits": [{}],
            "exchangeFilters": [],
            "symbols": [
                {
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "status": "TRADING",
                    "baseAsset": self.base_asset,
                    "baseAssetPrecision": 8,
                    "quoteAsset": self.quote_asset,
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "orderTypes": ["LIMIT", "LIMIT_MAKER"],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "permissionSets": [[
                        "SPOT",
                        "MARGIN"
                    ]]
                }
            ]
        }

    @property
    def initialize_verified_market_response(self):
        return {
            "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
            "chain_id": self.chain,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "state": "verified",
            "base_symbol": self.base_asset,
            "quote_symbol": self.quote_asset,
            "base_decimal": 18,
            "quote_decimal": 6,
            "base_precision": 6,
            "quote_precision": 10,
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
    def initialize_market_list_response(self):
        return self.all_symbols_request_mock_response

    @property
    def generated_typed_data_response(self):
        return {
            "message": "success",
            "data": {
                "limit_order": {
                    "chain_id": 80002,
                    "base_asset": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "quote_asset": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "side": 1,
                    "volume_precision": "100000000000000000",
                    "price_precision": "2700000000",
                    "order_hash": "0x5a28a76181ab0c008368ed09cc018b6d40eb23997b4a234cfe5650b7034d6611",  # noqa: mock
                    "raw_order_data": "{\"baseToken\":\"0x4200000000000000000000000000000000000006\",\"expiryTime\":\"0\",\"isBuy\":true,\"maker\":\"0x3da2b15eB80B1F7d499D18b6f0B671C838E64Cb3\",\"price\":\"2700000000\",\"quoteToken\":\"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913\",\"salt\":\"277564373322\",\"totalQuantity\":\"100000000000000000\"}",
                    "signature": None,
                    "signed_order_type": "tegro",
                    "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                    "market_symbol": "WETH_USDC"
                },
                "sign_data": {
                    "types": {
                        "EIP712Domain": [
                            {
                                "name": "name",
                                "type": "string"
                            },
                            {
                                "name": "version",
                                "type": "string"
                            },
                            {
                                "name": "chainId",
                                "type": "uint256"
                            },
                            {
                                "name": "verifyingContract",
                                "type": "address"
                            }
                        ],
                        "Order": [
                            {
                                "name": "baseToken",
                                "type": "address"
                            },
                            {
                                "name": "quoteToken",
                                "type": "address"
                            },
                            {
                                "name": "price",
                                "type": "uint256"
                            },
                            {
                                "name": "totalQuantity",
                                "type": "uint256"
                            },
                            {
                                "name": "isBuy",
                                "type": "bool"
                            },
                            {
                                "name": "salt",
                                "type": "uint256"
                            },
                            {
                                "name": "maker",
                                "type": "address"
                            },
                            {
                                "name": "expiryTime",
                                "type": "uint256"
                            }
                        ]
                    },
                    "primaryType": "Order",
                    "domain": {
                        "name": "TegroDEX",
                        "version": "1",
                        "chainId": 80002,
                        "verifyingContract": "0xa492c74aAc592F7951d98000a602A22157019563"  # noqa: mock
                    },
                    "message": {
                        "baseToken": "0x4200000000000000000000000000000000000006",
                        "expiryTime": "0",
                        "isBuy": True,
                        "maker": "0x3da2b15eB80B1F7d499D18b6f0B671C838E64Cb3",  # noqa: mock
                        "price": "2700000000",
                        "quoteToken": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                        "salt": "277564373322",
                        "totalQuantity": "100000000000000000"
                    }
                }
            }
        }

    @property
    def generated_cancel_typed_data_response(self):
        return {
            "limit_order": {
                "chain_id": 80001,
                "base_asset": "0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba",  # noqa: mock
                "quote_asset": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "side": 0,
                "volume_precision": "10000",
                "price_precision": "10000000",
                "order_hash": "0x23ef65f34e480bd9fea189b6f80ee62f71bdc4cea0bebc7599634c4b4bb7b82c",  # noqa: mock
                "raw_order_data": "{\"allowedSender\":\"0x0000000000000000000000000000000000000000\",\"interactions\":\"0x\",\"maker\":\"0xF3ef968DD1687DF8768a960E9D473a3361146A73\",\"makerAsset\":\"0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba\",\"makingAmount\":\"10000\",\"offsets\":\"0\",\"receiver\":\"0x0000000000000000000000000000000000000000\",\"salt\":\"96743852799\",\"takerAsset\":\"0xe5ae73187d0fed71bda83089488736cadcbf072d\",\"takingAmount\":\"10000000\"}",
                "signature": None,
                "signed_order_type": "tegro",
                "market_id": "80001_0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "market_symbol": "POKEBALLS_USDT"
            },
            "sign_data": {
                "types": {
                    "EIP712Domain": [
                        {
                            "name": "name",
                            "type": "string"
                        },
                        {
                            "name": "version",
                            "type": "string"
                        },
                        {
                            "name": "chainId",
                            "type": "uint256"
                        },
                        {
                            "name": "verifyingContract",
                            "type": "address"
                        }
                    ],
                    "CancelOrder": [
                        {
                            "name": "salt",
                            "type": "uint256"
                        },
                        {
                            "name": "makerAsset",
                            "type": "address"
                        },
                        {
                            "name": "takerAsset",
                            "type": "address"
                        },
                        {
                            "name": "maker",
                            "type": "address"
                        },
                        {
                            "name": "receiver",
                            "type": "address"
                        },
                        {
                            "name": "allowedSender",
                            "type": "address"
                        },
                        {
                            "name": "makingAmount",
                            "type": "uint256"
                        },
                        {
                            "name": "takingAmount",
                            "type": "uint256"
                        },
                        {
                            "name": "offsets",
                            "type": "uint256"
                        },
                        {
                            "name": "interactions",
                            "type": "bytes"
                        }
                    ]
                },
                "primaryType": "CancelOrder",
                "domain": {
                    "name": "Tegro",
                    "version": "5",
                    "chainId": 80001,
                    "verifyingContract": "0xa6bb5cfe9cc68e0affb0bb1785b6efdc2fe8d326"  # noqa: mock
                },
                "message": {
                    "allowedSender": "0x0000000000000000000000000000000000000000",
                    "interactions": "0x",
                    "maker": "0xF3ef968DD1687DF8768a960E9D473a3361146A73",  # noqa: mock
                    "makerAsset": "0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba",  # noqa: mock
                    "makingAmount": "10000",
                    "offsets": "0",
                    "receiver": "0x0000000000000000000000000000000000000000",
                    "salt": "96743852799",
                    "takerAsset": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "takingAmount": "10000000"
                }
            }
        }

    @property
    def order_creation_request_successful_mock_response(self):
        data = {
            "clientOrderId": "OID1",
            "order_id": "05881667-3bd3-4fc0-8b0e-db71c8a8fc99",
            "order_hash": "61c97934f3aa9d76d3e08dede89ff03a4c90aa9df09fe1efe055b7132f3b058d",  # noqa: mock
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": "buy",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 18,
            "quoteDecimals": 6,
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quantity": 0.009945,
            "quantityFilled": 0,
            "price": 2010.96,
            "avgPrice": 0,
            "pricePrecision": "2010960000",
            "volumePrecision": "9945498667303179",
            "total": 20,
            "fee": 0,
            "status": "Active",
            "cancel_reason": "",
            "timestamp": "2024-06-12T09:32:27.390651186Z"
        }
        return data

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {
                "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "balance": 15,
                "symbol": self.base_asset,
                "decimal": 4,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 22
            },
            {
                "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "balance": 2000,
                "symbol": self.quote_asset,
                "decimal": 4,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 22
            },
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {
                "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "balance": 15,
                "symbol": self.base_asset,
                "decimal": 4,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 22
            },
        ]

    @property
    def balance_event_websocket_update(self):
        return {}

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size= Decimal(0.01),
            min_price_increment=Decimal(
                f'1e-{self.trading_rules_request_mock_response[0]["quote_precision"]}'),
            min_base_amount_increment=Decimal(
                f'1e-{self.trading_rules_request_mock_response[0]["base_precision"]}'),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 28

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
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return TegroExchange(
            client_config_map=client_config_map,
            tegro_api_key=self.tegro_api_key,  # noqa: mock
            tegro_api_secret=self.tegro_api_secret,  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=CONSTANTS.DEFAULT_DOMAIN
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market_symbol"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(self.base_asset, Decimal(request_data["price"]))
        self.assertEqual(self.quote_asset, Decimal(request_data["quote_asset"]))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["data"]
        self.assertIsNone(request_params)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIsNone(request_params)

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
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
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
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
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
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
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2013, "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "order_submitted",
            "data": {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "order_hash": "26c9354ee66ced32f74a3c9ba388f80c155012accd5c1b10589d3a9a0d644b73",  # noqa: mock
                "order_id": order.exchange_order_id,
                "price": str(order.price),
                "pricePrecision": "300000000",
                "quantity": str(order.amount),
                "quantityFilled": 0,
                "quoteCurrency": self.quote_asset,
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "open",
                "timestamp": 1499405658657,
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "order_submitted",
            "data": {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "order_hash": "26c9354ee66ced32f74a3c9ba388f80c155012accd5c1b10589d3a9a0d644b73",  # noqa: mock
                "order_id": order.exchange_order_id,
                "price": str(order.price),
                "pricePrecision": "300000000",
                "quantity": str(order.amount),
                "quantityFilled": 0,
                "quoteCurrency": "alpha",
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "cancelled",
                "timestamp": 1499405658657,
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "action": "order_trade_processed",
            "data": {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "order_hash": "26c9354ee66ced32f74a3c9ba388f80c155012accd5c1b10589d3a9a0d644b73",  # noqa: mock
                "order_id": order.exchange_order_id,
                "price": str(order.price),
                "pricePrecision": "300000000",
                "quantity": str(order.amount),
                "quantityFilled": self.expected_fill_fee.flat_fees[0].token,
                "quoteCurrency": self.expected_fill_fee.flat_fees[0].token,
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "closed",
                "timestamp": 1499405658657,
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        return time.time()

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        return time.time()

    @aioresponses()
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
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

        url = web_utils.private_rest_url(CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "order_id": 99999,
            "id": 30000,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "price": "4.00000100",
            "amount": "12.00000000",
            "state": "success",
            "txHash": "0xf962a6b0c436f37a0a3ff049b51507b4e3c25226be752cf3b9944ad27a99a2a5",  # noqa: mock
            "timestamp": 1499865549590,
            "taker_type": "buy",
            "taker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3",  # noqa: mock
            "maker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3"  # noqa: mock
        }

        trade_fill_non_tracked_order = {
            "order_id": 99999,
            "id": 30000,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "price": "4.00000100",
            "amount": "12.00000000",
            "state": "success",
            "txHash": "0xf962a6b0c436f37a0a3ff049b51507b4e3c25226be752cf3b9944ad27a99a2a5",  # noqa: mock
            "timestamp": 1499865549590,
            "taker_type": "buy",
            "taker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3",  # noqa: mock
            "maker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3"  # noqa: mock
        }

        mock_response = [trade_fill, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["qty"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(trade_fill["commissionAsset"], Decimal(trade_fill["commission"]))],
                         fill_event.trade_fee.flat_fees)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(float(trade_fill_non_tracked_order["time"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["qty"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                trade_fill_non_tracked_order["commissionAsset"],
                Decimal(trade_fill_non_tracked_order["commission"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self.is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_fills_request_parameters(self, mock_api):
        self.exchange._set_current_timestamp(0)
        self.exchange._last_poll_timestamp = -1

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

        url = web_utils.private_rest_url(CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = []
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        self.exchange._last_trades_poll_tegro_timestamp = 10
        self.async_run_with_timeout(self.exchange._all_trade_updates_for_order())

    @aioresponses()
    def test_update_order_fills_from_trades_with_repeated_fill_triggers_only_one_event(self, mock_api):
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

        url = web_utils.private_rest_url(CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill_non_tracked_order = {
            "id": 30000,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "price": "4.00000100",
            "amount": "12.00000000",
            "state": "success",
            "txHash": "0xf962a6b0c436f37a0a3ff049b51507b4e3c25226be752cf3b9944ad27a99a2a5",  # noqa: mock
            "timestamp": 1499865549590,
            "taker_type": "buy",
            "taker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3",  # noqa: mock
            "maker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3"  # noqa: mock
        }

        mock_response = [trade_fill_non_tracked_order, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(float(trade_fill_non_tracked_order["timestamp"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["amount"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(self.base_asset,
                        Decimal(0))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self.is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

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

        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "order_id": str(order.exchange_order_id),
            "orderHash": "f27c235af9a19d8539d1a142b000f6370afd8a53a67c4d432504e4e8d7b9bbff",  # noqa: mock
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": "buy",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 18,
            "quoteDecimals": 6,
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quantity": 1,
            "quantityFilled": 0,
            "price": 10000,
            "avgPrice": 10000.0,
            "pricePrecision": "1000000000",
            "volumePrecision": "0",
            "total": 5,
            "fee": 0,
            "status": "cancelled",
            "cancel_reason": "",
            "timestamp": 1499827319559
        }
        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={order_status['timestamp'] * 1e-3}, new_state={repr(OrderState.FAILED)}, "
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
            "order_id": str(order.exchange_order_id),
            "price": 1000.0000000,
            "pricePrecision": "3079999999",
            "quantity": 1.00000000,
            "quantityFilled": 1.00000000,
            "quoteCurrency": self.quote_asset,
            "quoteDecimals": 6,
            "side": "buy",
            "status": "cancelled",
            "timestamp": 1499405658657,
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

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
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
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_time_synchronizer_related_request_error_detection(self):
        pass

    @aioresponses()
    def test_place_order_manage_server_overloaded_error_unkown_order(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
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

        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
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
        pass

    def test_format_trading_rules__notional_but_no_min_notional_present(self):
        pass

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        pass

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "cancelled_order_ids": [str(order.exchange_order_id)],
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "closed",
            "cancel": {
                "reason": "",
                "code": 0
            },
            "timestamp": 1499827319559
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "cancelled",
            "cancel": {
                "reason": "user_cancel",
                "code": 611
            },
            "timestamp": 1499827319559
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "open",
            "cancel": {
                "reason": "",
                "code": 0
            },
            "timestamp": 1499827319559
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "open",
            "cancel": {
                "reason": "",
                "code": 0
            },
            "timestamp": 1499827319559
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": str(self.expected_partial_fill_price),
                "amount": str(self.expected_partial_fill_amount),
                "state": "partial",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "taker_type": order.order_type.name.lower(),
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "id": self.expected_fill_trade_id,
                "orderId": str(order.exchange_order_id),
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": int(order.price),
                "amount": str(order.amount),
                "state": "success",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "taker_type": order.order_type.name.lower(),
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]
