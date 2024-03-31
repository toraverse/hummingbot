import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_api_order_book_data_source import TegroAPIOrderBookDataSource
from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class TegroAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "KRYPTONITE"
        cls.quote_asset = "USDT"
        cls.tegro_api_key = "",
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "tegro"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = TegroExchange(
            client_config_map=client_config_map,
            tegro_api_key="",
            tegro_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.data_source = TegroAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                       connector=self.connector,
                                                       api_factory=self.connector._web_assistants_factory,
                                                       domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _successfully_subscribed_event(self):
        resp = {
            "action": "subscribe",
            "channelId": "0x0a0cdc90cc16a0f3e67c296c8c0f7207cbdc0f4e"  # noqa: mock
        }
        return resp

    def _trade_update_event(self):
        resp = {
            "action": "trade_updated",
            "data": {
                "amount": 1,
                "id": "68a22415-3f6b-4d27-8996-1cbf71d89e5f",
                "maker": "0xf3ef968dd1687df8768a960e9d473a3361146a73",  # noqa: mock
                "marketId": "",
                "price": 0.1,
                "state": "success",
                "symbol": self.ex_trading_pair,
                "taker": "0xf3ef968dd1687df8768a960e9d473a3361146a73",  # noqa: mock
                "takerType": "buy",
                "time": '2024-02-11T22:31:50.25114Z',
                "txHash": "0x2f0d41ced1c7d21fe114235dfe363722f5f7026c21441f181ea39768a151c205",  # noqa: mock
            }}
        return resp

    def _order_diff_event(self):
        resp = {
            "action": "order_book_diff",
            "data": {
                "timestamp": 1709294334,
                "symbol": self.ex_trading_pair,
                "bids": [
                    {
                        "price": "60.9700",
                        "price_float": 0.0061,
                        "quantity": "1600",
                        "quantity_float": 0.16
                    },
                ],
                "asks": [
                    {
                        "price": "71.29",
                        "price_float": 0.0071,
                        "quantity": "50000",
                        "quantity_float": 5
                    },
                ]
            }}
        return resp

    def _snapshot_response(self):
        resp = {
            "timestamp": 1709294334,
            "Bids": [
                {
                    "price": "6097.00",
                    "price_float": 0.61,
                    "quantity": "1600",
                    "quantity_float": 0.16
                },
            ],
            "Asks": [
                {
                    "price": "7129",
                    "price_float": 0.071,
                    "quantity": "50000",
                    "quantity_float": 5
                },
            ]
        }
        return resp

    def _market_list_response(self):
        resp = [
            {
                "BaseContractAddress": "0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba",  # noqa: mock
                "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "ChainId": 80001,
                "ID": "80001_0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "Symbol": "POKEBALLS_USDT",
                "State": "verified",
                "BaseSymbol": "POKEBALLS",
                "QuoteSymbol": "USDT",
                "BaseDecimal": 4,
                "QuoteDecimal": 4,
                "CreatedAt": "2024-01-08T16:36:20.92852Z",
                "UpdatedAt": "2024-01-08T16:36:20.92852Z",
                "ticker": {
                    "base_volume": 0,
                    "quote_volume": 0,
                    "price": 0.0065,
                    "price_change_24h": 0,
                    "price_high_24h": 0,
                    "price_low_24h": 0,
                    "ask_low": 0,
                    "bid_high": 0
                }
            },
            {
                "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",  # noqa: mock
                "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "ChainId": 80001,
                "ID": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "Symbol": "KRYPTONITE_USDT",
                "State": "verified",
                "BaseSymbol": "KRYPTONITE",
                "QuoteSymbol": "USDT",
                "BaseDecimal": 4,
                "QuoteDecimal": 4,
                "CreatedAt": "2024-01-08T16:36:40.365473Z",
                "UpdatedAt": "2024-01-08T16:36:40.365473Z",
                "ticker": {
                    "base_volume": 0,
                    "quote_volume": 0,
                    "price": 58,
                    "price_change_24h": 0,
                    "price_high_24h": 0,
                    "price_low_24h": 0,
                    "ask_low": 0,
                    "bid_high": 0
                }
            }
        ]
        return resp

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self._snapshot_response()

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = resp["timestamp"]

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(6097, bids[0].price)
        self.assertEqual(1600, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(7129, asks[0].price)
        self.assertEqual(50000, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @aioresponses()
    def test_fetch_market_data(
            self,
            mock_api) -> str:
        url = web_utils.private_rest_url(CONSTANTS.MARKET_LIST_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._market_list_response()
        mock_api.get(regex_url, body=json.dumps(response))
        return response

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe = {
            "code": None,
            "id": 1
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        print(sent_subscription_messages)
        expected_trade_subscription = {
            "action": "subscribe",
            "channelId": f"{CONSTANTS.CHAIN_ID}/0x6464e14854d58feb60e130873329d77fcd2d8eb7"  # noqa: mock
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())
        print(msg.trade_id)

        self.assertEqual("68a22415-3f6b-4d27-8996-1cbf71d89e5f", msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self._order_diff_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(diff_event["data"]["timestamp"], msg.update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError, repeat=True)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.exchange.tegro.tegro_api_order_book_data_source"
           ".TegroAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception, repeat=True)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(1709294334, msg.update_id)
