import asyncio
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import eth_account
from bidict import bidict
from eth_account import Account, messages

from hummingbot.client.performance import PerformanceMetrics
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_utils, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_api_order_book_data_source import TegroAPIOrderBookDataSource
from hummingbot.connector.exchange.tegro.tegro_api_user_stream_data_source import TegroUserStreamDataSource
from hummingbot.connector.exchange.tegro.tegro_auth import TegroAuth
from hummingbot.connector.exchange.tegro.tegro_messages import encode_typed_data
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule

# from hummingbot.connector.utils import TradeFillOrderDetails
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.gateway_config_utils import SUPPORTED_CHAINS
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

# from hummingbot.core.event.events import (
#     MarketEvent,
#     OrderFilledEvent,
# )


if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_0 = Decimal(0)
s_float_NaN = float("nan")


class TegroExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    _markets = {}
    _market = {}

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 tegro_api_key: str,
                 tegro_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DOMAIN
                 ):
        self.api_key = tegro_api_key
        self.secret_key = tegro_api_secret
        self._api_factory = WebAssistantsFactory
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_tegro_timestamp = 1.0
        super().__init__(client_config_map)
        self.real_time_balance_update = False

    @staticmethod
    def tegro_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(tegro_type: str) -> OrderType:
        return OrderType[tegro_type]

    @property
    def authenticator(self):
        return TegroAuth(
            api_key=self.api_key,
            api_secret=self.secret_key
        )

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def wallet(self):
        return eth_account.Account.from_key(self.secret_key)

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        params = {"chain_id": CONSTANTS.CHAIN_ID, "verified": "true", "page": 1, "page_size": 20, "sort_order": "desc"}
        pairs_prices = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL, params=params)

        pairs_prices = pairs_prices["ticker"]
        for pairs_price in pairs_prices:
            price = pairs_price["price"]
        return price

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return TegroAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return TegroUserStreamDataSource(
            auth=self._auth,
            domain=self.domain,
            throttler=self._throttler,
            api_factory=self._web_assistants_factory,
        )

    async def _initialize_market_list(self):
        params = {"chain_id": CONSTANTS.CHAIN_ID, "verified": "true", "page": 1, "page_size": 20, "sort_order": "desc"}
        try:
            self._markets = await self._api_request(
                path_url=CONSTANTS.MARKET_LIST_PATH_URL,
                params=params,
                method=RESTMethod.GET,
                limit_id=CONSTANTS.MARKET_LIST_PATH_URL,
            )
        except Exception:
            self.logger().error(
                "Unexpected error occurred fetching market data...", exc_info=True
            )
            raise

    async def _initialize_verified_market(self, trading_pair: str):
        sym = trading_pair.replace('_', '-')
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=sym)
        params = {"chain_id": CONSTANTS.CHAIN_ID, "market_symbol": symbol}
        try:
            self._market = await self._api_request(
                path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
                params=params,
                method=RESTMethod.GET,
                limit_id=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            )
        except Exception:
            self.logger().error(
                "Unexpected error occurred fetching market data...", exc_info=True
            )
            raise

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = tegro_utils.get_client_order_id(True)
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = tegro_utils.get_client_order_id(False)
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price,
                           **kwargs) -> Tuple[str, float]:
        transaction_data = await self.generate_typed_data(amount, order_type, price, trade_type, trading_pair)
        pr = int(transaction_data["data"]["sign_data"]["message"]["price"])
        am = int(transaction_data["data"]["sign_data"]["message"]["totalQuantity"])
        isb = transaction_data["data"]["sign_data"]["message"]["isBuy"]
        sa = int(transaction_data["data"]["sign_data"]["message"]["salt"])
        bt = transaction_data["data"]["sign_data"]["message"]["baseToken"]
        qt = transaction_data["data"]["sign_data"]["message"]["quoteToken"]
        ma = transaction_data["data"]["sign_data"]["message"]["maker"]
        s = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        symbol: str = s.replace('-', '_')

        # datas to sign
        domain_data = {
            "name": "TegroDEX",
            "version": "1",
            "chainId": 80001,
            "verifyingContract": "0xb546E4a749e71Ef8F64D8686a21FF3960BF3Bb0B",
        }
        message_data = {
            "baseToken": bt,
            "isBuy": isb,
            "maker": ma,
            "price": pr,
            "quoteToken": qt,
            "salt": sa,
            "totalQuantity": am,
        }
        message_types = {
            "Order": [
                {"name": "baseToken", "type": "address"},
                {"name": "quoteToken", "type": "address"},
                {"name": "price", "type": "uint256"},
                {"name": "totalQuantity", "type": "uint256"},
                {"name": "isBuy", "type": "bool"},
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
            ],
        }

        # encode and sign
        structured_data = encode_typed_data(domain_data, message_types, message_data)
        signed = self.wallet.sign_message(structured_data)
        signature = signed.signature.hex()

        api_params = {
            "chain_id": 80001,
            "side": transaction_data["data"]["limit_order"]["side"],
            "volume_precision": transaction_data["data"]["limit_order"]["volume_precision"],
            "price_precision": transaction_data["data"]["limit_order"]["price_precision"],
            "order_hash": transaction_data["data"]["limit_order"]["order_hash"],
            "raw_order_data": transaction_data["data"]["limit_order"]["raw_order_data"],
            "signature": signature,
            "signed_order_type": "tegro",
            "market_id": transaction_data["data"]["limit_order"]["market_id"],
            "market_symbol": symbol,
        }
        try:
            data = await self._api_request(
                path_url=CONSTANTS.ORDER_PATH_URL,
                method=RESTMethod.POST,
                data=api_params,
                is_auth_required=False,
                limit_id=CONSTANTS.ORDER_PATH_URL,
            )
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = ("status is 503" in error_description
                                    and "Unknown error, please check your request or try again later." in error_description)
            if is_server_overloaded:
                o_id = "Unknown"
                transact_time = int(datetime.now(timezone.utc).timestamp() * 1e3)
            else:
                raise
        o_id = str(data["data"]["orderId"])
        transact_time = tegro_utils.datetime_val_or_now(data["data"]["timestamp"], on_error_return_now=True).timestamp(),
        return o_id, transact_time

    async def generate_typed_data(self, amount, order_type, price, trade_type, trading_pair) -> Dict[str, Any]:
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        params = {
            "chain_id": CONSTANTS.CHAIN_ID,
            "market_symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "side": side_str,
            "wallet_address": self.api_key,
            "amount": math.floor(amount),
        }
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            price_str = math.floor(price)
            params["price"] = price_str
        data = await self._api_request(
            path_url=CONSTANTS.GENERATE_SIGN_URL,
            method=RESTMethod.POST,
            data=params,
            is_auth_required=False,
            limit_id=CONSTANTS.GENERATE_SIGN_URL,
        )
        if data["message"] != "success":
            raise IOError(f"Error submitting order {data}")
        return data

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        address = self.api_key.lower()
        structured_data = messages.encode_defunct(text=address)
        sign = Account.sign_message(structured_data, self.secret_key)
        signature = sign.signature.hex()
        params = {
            "id": str(tracked_order.exchange_order_id),
            "chain_id": CONSTANTS.CHAIN_ID,
            "WalletAddress": self.api_key,
            "signature": signature,
        }
        cancel_result = await self._api_request(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            method=RESTMethod.POST,
            data=params,
            is_auth_required=False,
            limit_id=CONSTANTS.CANCEL_ORDER_URL
        )
        print(cancel_result["message"])
        if cancel_result["message"] == "Order Cancel request is successful.":

            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
            {
                "BaseContractAddress": "0x6464e14854d58feb60e130873329d77fcd2d8eb7",
                "QuoteContractAddress": "0xe5ae73187d0fed71bda83089488736cadcbf072d",
                "ChainId": 80001,
                "ID": "80001_0x6464e14854d58feb60e130873329d77fcd2d8eb7_0xe5ae73187d0fed71bda83089488736cadcbf072d",
                "Symbol": "KRYPTONITE_USDT",
                "State": "verified",
                "BaseSymbol": "KRYPTONITE",
                "QuoteSymbol": "USDT",
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
        """
        trading_pair_rules = exchange_info_dict
        retval = []
        for rule in filter(tegro_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("Symbol"))
                min_order_size = Decimal(1)
                min_price_inc = PerformanceMetrics.smart_round(Decimal(str(rule["ticker"]['ask_low'])), 4)
                min_amount_inc = Decimal(1)
                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=min_price_inc,
                                min_base_amount_increment=min_amount_inc))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    # async def _status_polling_loop_fetch_updates(self):
    #     await self._update_order_fills_from_trades()
    #     await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = CONSTANTS.USER_METHODS
        async for event_message in self._iter_user_event_queue():
            try:
                channel: str = event_message.get("action", None)
                results: Dict[str, Any] = event_message.get("data", {})
                if "code" not in event_message and channel not in user_channels.values():
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue
                if channel == CONSTANTS.USER_METHODS["TRADES_CREATE"]:
                    self._process_trade_message(results)
                if channel == CONSTANTS.USER_METHODS["TRADES_UPDATE"]:
                    self._process_trade_message(results)
                elif channel == CONSTANTS.USER_METHODS["ORDER_PLACED"]:
                    self._process_order_message(results)
                elif channel == CONSTANTS.USER_METHODS["ORDER_SUBMITTED"]:
                    self._process_order_message(results)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _create_trade_update_with_order_fill_data(
            self,
            order_fill: Dict[str, Any],
            order: InFlightOrder):
        base_currency = order_fill["symbol"].split("_")[0],

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,

            percent_token=base_currency,
            flat_fees=[TokenAmount(
                amount=Decimal(0),
                token=base_currency,
            )]
        )

        trade_update = TradeUpdate(
            trade_id=str(order_fill["id"]),
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(order_fill["amount"]),
            fill_quote_amount=Decimal(order_fill["amount"]),
            fill_price=Decimal(order_fill["price"]),
            fill_timestamp=tegro_utils.datetime_val_or_now(order_fill['time'], on_error_return_now=True).timestamp(),
        )
        return trade_update

    def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        client_order_id = trade["id"] is None and '' or str(trade["id"])
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
        else:
            trade_update = self._create_trade_update_with_order_fill_data(
                order_fill=trade,
                order=tracked_order)
            self._order_tracker.process_trade_update(trade_update)

    def _create_order_update_with_order_status_data(self, order_status: Dict[str, Any], order: InFlightOrder):
        formatted_time = tegro_utils.datetime_val_or_now(order_status['time'], on_error_return_now=True).timestamp()
        client_order_id = str(order_status.get("orderId", ""))
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=int(formatted_time),
            new_state=CONSTANTS.ORDER_STATE[order_status["status"]],
            client_order_id=client_order_id,
            exchange_order_id=str(order_status["orderId"]),
        )
        return order_update

    def _process_order_message(self, raw_msg: Dict[str, Any]):
        order_msg = raw_msg.get("data", {})
        client_order_id = str(order_msg.get("orderId", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        order_update = self._create_order_update_with_order_status_data(order_status=raw_msg, order=tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    async def _users_orders(self, trading_pair: str):
        await self._initialize_verified_market(trading_pair)
        user_orders = await self._api_get(
            path_url=CONSTANTS.ORDER_LIST.format(self.api_key),
            params={"chain_id": CONSTANTS.CHAIN_ID,
                    "market_id": f'{self._market["market"]["ID"]}',
                    "statuses": "matched"},
            limit_id=CONSTANTS.ORDER_LIST,
            is_auth_required=False,
            headers={"Content-Type": "application/json"}
        )
        return user_orders

    async def _user_trades(self):
        # Gather user orders for each trading pair concurrently
        tasks = [self._users_orders(trading_pair=trading_pair) for trading_pair in self.trading_pairs]
        orders_results = await safe_gather(*tasks, return_exceptions=True)

        # Collect order IDs from the results
        order_ids = []
        for orders in orders_results:
            for order in orders:
                order_ids.append(str(order["orderId"]))

        # Fetch trades for each order concurrently
        tasks = [self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order_id),
            limit_id=CONSTANTS.TRADES_FOR_ORDER_PATH_URL,
            is_auth_required=False
        ) for order_id in order_ids]
        trades_results = await safe_gather(*tasks, return_exceptions=True)

        # Add order ID to each trade data
        for order_id, trades_data in zip(order_ids, trades_results):
            if isinstance(trades_data, Exception):
                # Handle errors appropriately
                print(f"Error fetching trades for order ID {order_id}: {trades_data}")
            else:
                for trade_data in trades_data:
                    trade_data['orderId'] = order_id

        # Organize trades data by trading pair
        user_trades = []
        for trades_data in trades_results:
            user_trades.append(trades_data[0])

        return user_trades

    # async def _update_order_fills_from_trades(self):
    #     """
    #     This is intended to be a backup measure to get filled events with trade ID for orders,
    #     in case Tegro's user stream events are not working.
    #     NOTE: It is not required to copy this functionality in other connectors.
    #     This is separated from _update_order_status which only updates the order status without producing filled
    #     events, since Tegro's get order endpoint does not return trade IDs.
    #     The minimum poll interval for order status is 10 seconds.
    #     """
    #     small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
    #     small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
    #     long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
    #     long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

    #     if (long_interval_current_tick > long_interval_last_tick
    #             or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
    #         self._last_trades_poll_tegro_timestamp = self._time_synchronizer.time()
    #         order_by_exchange_id_map = {}
    #         for order in self._order_tracker.all_fillable_orders.values():
    #             order_by_exchange_id_map[order.exchange_order_id] = order

    #         trading_pairs = self.trading_pairs

    #         user_trades = await self._user_trades()

    #         for trade, trading_pair in zip(user_trades, trading_pairs):

    #             if isinstance(trade, Exception):
    #                 self.logger().network(
    #                     f"Error fetching trades update for the order {trading_pair}: {trade}.",
    #                     app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
    #                 )
    #                 continue
    #             exchange_order_id = trade["orderId"]
    #             if exchange_order_id in order_by_exchange_id_map:
    #                 # This is a fill for a tracked order
    #                 symbol = trade["symbol"].split('-')[0]
    #                 tracked_order = order_by_exchange_id_map[exchange_order_id]
    #                 fee = TradeFeeBase.new_spot_fee(
    #                     fee_schema=self.trade_fee_schema(),
    #                     trade_type=tracked_order.trade_type,
    #                     percent_token=symbol,
    #                     flat_fees=[TokenAmount(amount=Decimal(0), token=symbol)]
    #                 )
    #                 trade_update = TradeUpdate(
    #                     trade_id=trade["id"],
    #                     client_order_id=tracked_order.client_order_id,
    #                     exchange_order_id=exchange_order_id,
    #                     trading_pair=trading_pair,
    #                     fee=fee,
    #                     fill_base_amount=Decimal(trade["amount"]),
    #                     fill_quote_amount=Decimal(trade["amount"]),
    #                     fill_price=Decimal(trade["price"]),
    #                     fill_timestamp=tegro_utils.datetime_val_or_now((trade['time']), on_error_return_now=True).timestamp(),
    #                 )
    #                 self._order_tracker.process_trade_update(trade_update)

    #             elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
    #                 symbol = trade["symbol"].split('-')[0]
    #                 # This is a fill of an order registered in the DB but not tracked any more
    #                 self._current_trade_fills.add(TradeFillOrderDetails(
    #                     market=self.display_name,
    #                     exchange_trade_id=trade["id"],
    #                     symbol=trading_pair))
    #                 self.trigger_event(
    #                     MarketEvent.OrderFilled,
    #                     OrderFilledEvent(
    #                         timestamp=tegro_utils.datetime_val_or_now(trade.get('time'), on_error_return_now=True).timestamp(),
    #                         order_id=self._exchange_order_ids.get(trade["orderId"], None),
    #                         trading_pair=trading_pair,
    #                         trade_type=TradeType.BUY if trade.get("takerType") == "buy" else TradeType.SELL,
    #                         order_type=OrderType.LIMIT,
    #                         price=tegro_utils.decimal_val_or_none(trade["price"]),
    #                         amount=tegro_utils.decimal_val_or_none(trade["amount"]),
    #                         trade_fee=DeductedFromReturnsTradeFee(
    #                             flat_fees=[
    #                                 TokenAmount(
    #                                     symbol,
    #                                     Decimal(0)
    #                                 )
    #                             ]
    #                         ),
    #                         exchange_trade_id=str(tegro_utils.str_val_or_none(trade.get("id"), on_error_return_none=False)),
    #                     ))
    #                 self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = str(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            await self._initialize_verified_market(trading_pair=trading_pair)
            all_fills_response = await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id),
                is_auth_required=False,
                limit_id=CONSTANTS.TRADES_FOR_ORDER_PATH_URL)

            for trade in all_fills_response:
                timestamp = datetime.strptime(trade["time"], '%Y-%m-%dT%H:%M:%S.%fZ')
                formatted_time = timestamp.strftime('%Y%m%d')

                exchange_order_id = order.exchange_order_id
                symbol = trade["symbol"].split('-')[0]
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=symbol,
                    flat_fees=[TokenAmount(amount=Decimal(0), token=symbol)]
                )

                trade_update = TradeUpdate(
                    trade_id=trade["id"],
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["amount"]),
                    fill_quote_amount=Decimal(trade["amount"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=formatted_time,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        await self._initialize_verified_market(trading_pair=tracked_order.trading_pair)

        # Fetch the list of orders from the API
        orders = await self._fetch_orders()
        # Find the order with the matching exchange_order_id
        order_data = self._find_order_by_id(orders, tracked_order.exchange_order_id)
        # Parse the order data and construct the OrderUpdate object
        order_update = self._parse_order_update(order_data, tracked_order)

        return order_update

    async def _fetch_orders(self) -> List[dict]:
        """
        Fetches the list of orders from the API.
        """
        params = {
            "chain_id": CONSTANTS.CHAIN_ID,
            "market_id": str(self._market["market"]["ID"])
        }

        response = await self._api_get(
            path_url=CONSTANTS.ORDER_LIST.format(self.api_key),
            params=params,
            limit_id=CONSTANTS.ORDER_LIST,
            is_auth_required=False,
            headers={"Content-Type": "application/json"}
        )
        return response

    def _find_order_by_id(self, orders: List[dict], order_id: str) -> dict:
        """
        Finds the order with the specified order_id in the list of orders.
        """
        for order in orders:
            if order["orderId"] == order_id:
                return order

        raise Exception(f"Order {order_id} not found in order status update response.")

    def _parse_order_update(self, order_data: dict, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Parses the order data and constructs the OrderUpdate object.
        """
        if not order_data:
            raise Exception("Order data is empty.")

        new_state = CONSTANTS.ORDER_STATE.get(order_data.get("status", ""))
        timestamp = datetime.strptime(order_data["time"], '%Y-%m-%dT%H:%M:%S.%fZ')
        formatted_time = timestamp.strftime('%Y%m%d')

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=formatted_time,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        symbols = set()

        await self._initialize_market_list()
        data = set()
        for res in self._markets:
            data.update((res["BaseSymbol"], res["QuoteSymbol"]))

        all_asset_names = data
        symbols.update(SUPPORTED_CHAINS)
        symbols.update(all_asset_names)

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL.format(f"{CONSTANTS.CHAIN_ID}/{self.api_key}"),
            limit_id=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=False)

        balances = account_info
        for balance_entry in balances:
            asset_name = balance_entry["symbol"]
            if asset_name in symbols:
                free_balance = Decimal(balance_entry["balance"])
                total_balance = Decimal(balance_entry["balance"])
                self._account_available_balances[asset_name] = free_balance
                self._account_balances[asset_name] = total_balance
                remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset in asset_names_to_remove:
            del self._account_available_balances[asset]
            del self._account_balances[asset]

    async def _initialize_trading_pair_symbol_map(self):
        try:
            params = {"chain_id": CONSTANTS.CHAIN_ID, "verified": "true", "page": 1, "page_size": 20, "sort_order": "desc"}
            exchange_info = await self._api_get(path_url=self.trading_pairs_request_path, params=params)
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()

        for entry in filter(tegro_utils.is_exchange_information_valid, exchange_info):
            base, quote = entry['Symbol'].split('_')

            mapping[entry["Symbol"]] = combine_to_hb_trading_pair(
                base=base,
                quote=quote
            )

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "chain_id": CONSTANTS.CHAIN_ID,
        }
        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            params=params
        )

        return float(resp_json["market"]["ticker"]["price"])

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path,
                            params = {"chain_id": CONSTANTS.CHAIN_ID, "verified": "true", "page": 1, "page_size": 20, "sort_order": "desc"},
                            headers={"Content-Type": "application/json"})

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path,
                                            params = {"chain_id": CONSTANTS.CHAIN_ID, "verified": "true", "page": 1, "page_size": 20, "sort_order": "desc"},
                                            headers={"Content-Type": "application/json"})
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(
            path_url=self.trading_pairs_request_path,
            params = {"chain_id": CONSTANTS.CHAIN_ID, "verified": "true", "page": 1, "page_size": 20, "sort_order": "desc"},
            headers={"Content-Type": "application/json"})
        return exchange_info
