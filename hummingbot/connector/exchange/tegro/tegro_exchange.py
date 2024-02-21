import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from web3 import HTTPProvider, Web3

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_utils, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_api_order_book_data_source import TegroAPIOrderBookDataSource
from hummingbot.connector.exchange.tegro.tegro_api_user_stream_data_source import TegroUserStreamDataSource
from hummingbot.connector.exchange.tegro.tegro_auth import TegroAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_0 = Decimal(0)
s_float_NaN = float("nan")


class TegroExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    _markets = {}

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 tegro_api_key: str,
                 tegro_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DOMAIN
                 ):
        self.secret_key = tegro_api_secret
        self.api_key = tegro_api_key
        self._provider_url = CONSTANTS.TEGRO_BASE_URL
        self._provider = Web3(HTTPProvider(self._provider_url))
        self._api_factory = WebAssistantsFactory
        self.client_config_map = client_config_map
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_tegro_timestamp = 1.0
        super().__init__(client_config_map)

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
    def market(self):
        return self._markets

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
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.TICKER_BOOK_PATH_URL

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
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL, params=params)

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
        try:
            params = {"chain_id": CONSTANTS.CHAIN_ID, "verified": "true", "page": 1, "page_size": 20, "sort_order": "desc"}
            self._markets = await self._api_get(path_url=self.check_network_request_path, params=params)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

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

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Optional[Decimal] = None):
        """
        Creates a an order in the exchange using the parameters to configure it

        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        exchange_order_id = ""
        trading_rule = self._trading_rules[trading_pair]

        if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
            order_type = OrderType.LIMIT
            price = self.quantize_order_price(trading_pair, price)
        quantized_amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=quantized_amount
        )
        if not price or price.is_nan() or price == s_decimal_0:
            current_price: Decimal = self.get_price(trading_pair, False)
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        if order_type not in self.supported_order_types():
            self.logger().error(f"{order_type} is not in the list of supported order types")
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)
            return

        if quantized_amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order "
                                  f"size {trading_rule.min_order_size}. The order will not be created, increase the "
                                  f"amount to be higher than the minimum order size.")
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)
            return

        if notional_size < trading_rule.min_notional_size:
            self.logger().warning(f"{trade_type.name.title()} order notional {notional_size} is lower than the "
                                  f"minimum notional size {trading_rule.min_notional_size}. The order will not be "
                                  f"created. Increase the amount or the price to be higher than the minimum notional.")
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)
            return

        try:
            exchange_order_id, update_timestamp = await self._place_order(
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                trade_type=trade_type,
                order_type=order_type,
                price=price)

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                update_timestamp=update_timestamp,
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)

            return order_id, exchange_order_id

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to {self.name_cap} for "
                f"{amount.normalize()} {trading_pair} {price.normalize()}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit {trade_type.name.lower()} order to {self.name_cap}. Check API key and network connection."
            )
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)

    async def generate_typed_data(self, amount: str, order_type: OrderType, price: Decimal, trade_type: TradeType,) -> Dict[str, Any]:
        trading_pairs = self._trading_pairs
        amount_str = f"{amount}"
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        params = {
            "market_symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pairs),
            "chain_id": CONSTANTS.CHAIN_ID,
            "wallet_address": self.api_key,
            "side": side_str,
            "amount": amount_str,
        }
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            price_str = f"{price:f}"
            params["price"] = price_str
        data_resp = await self._api_post(
            path_url=web_utils.public_rest_url(path_url=CONSTANTS.GENERATE_SIGN_URL, domain=self._domain),
            params=params
        )
        return data_resp

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        transaction_data = await self.generate_typed_data(amount, order_type, price, trade_type)
        s = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        symbol: str = s.replace('-', '_')
        message = json.dumps({
            **transaction_data["data"]["sign_data"]["domain"],
            **{"Order": transaction_data["data"]["sign_data"]["types"]["Order"]},
            **json.loads(transaction_data["data"]["limit_order"]["raw_order_data"])
        }).encode("utf-8")

        # Sign the message using the private key
        signature = await self._provider.eth.account.sign_message(message, self.secret_key)

        api_params = {
            "market_symbol": symbol,
            "chain_id": CONSTANTS.CHAIN_ID,
            "side": transaction_data["data"]["limit_order"]["side"],
            "volume_precision": transaction_data["data"]["limit_order"]["volume_precision"],
            "price_precision": transaction_data["data"]["limit_order"]["price_precision"],
            "raw_order_data": transaction_data["data"]["limit_order"]["raw_order_data"],
            "market_id": transaction_data["data"]["limit_order"]["market_id"],
            "signed_order_type": transaction_data["limit_order"]["signed_order_type"],
            "signature": signature
        }
        try:
            data = await self._api_post(
                path_url=CONSTANTS.ORDER_PATH_URL,
                params=api_params,
                is_auth_required=False
            )
            o_id = str(data["id"])
            transact_time = data["timestamp"] * 1e-3
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = ("status is 503" in error_description
                                    and "Unknown error, please check your request or try again later." in error_description)
            if is_server_overloaded:
                o_id = "Unknown"
                transact_time = int(datetime.now(timezone.utc).timestamp() * 1e3)
            else:
                raise
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        params = {
            "ChainID": CONSTANTS.CHAIN_ID,
            "WalletAddress": self.api_key,
        }

        try:
            cancel_result = await self._api_put(
                path_url=CONSTANTS.CANCEL_ORFDER_URL.format(order_id),
                data=params,
                is_auth_required=True)
        except OSError as e:
            if "HTTP status is 404" in str(e):
                return True
            raise e
        if len(cancel_result) > 0:
            if cancel_result.get("data")[0].get('id') == tracked_order.exchange_order_id:
                return True

        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        pass

    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("action")
                # Refer to https://github.com/tegro-exchange/tegro-official-api-docs/blob/master/user-data-stream.md
                # As per the order update section in Tegro the ID of the order being canceled is under the "C" key
                if event_type == "order_placed":
                    execution_type = event_message.get("status")
                    if execution_type != "Cancelled":
                        client_order_id = event_message.get("orderId")
                    else:
                        client_order_id = event_message.get("orderId")

                    if execution_type == "Matched":
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is not None:
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=event_message["baseCurrency"],
                                flat_fees=[TokenAmount(amount=Decimal(0), token=event_message["baseCurrency"])]
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(event_message["id"]),
                                client_order_id=client_order_id,
                                exchange_order_id=str(event_message["orderId"]),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(event_message["quantity"]),
                                fill_quote_amount=Decimal(event_message["quantyty"]) * Decimal(event_message["price"]),
                                fill_price=Decimal(event_message["price"]),
                                fill_timestamp=event_message["timestamp"] * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_message["time"] * 1e-3,
                            new_state=CONSTANTS.ORDER_STATE[event_message["status"]],
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message["orderId"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "outboundAccountPosition":
                    balances = event_message["B"]
                    for balance_entry in balances:
                        asset_name = balance_entry["a"]
                        free_balance = Decimal(balance_entry["f"])
                        total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Tegro's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Tegro's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if (long_interval_current_tick > long_interval_last_tick
                or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            query_time = int(self._last_trades_poll_tegro_timestamp * 1e3)
            self._last_trades_poll_tegro_timestamp = self._time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self._order_tracker.all_fillable_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                params = {
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                    "chain_id": CONSTANTS.CHAIN_ID,
                    "market_id": f'{self._markets["ID"]}',
                }
                if self._last_poll_timestamp > 0:
                    params["startTime"] = query_time
                tasks.append(self._api_get(
                    path_url=CONSTANTS.TRADES_PATH_URL,
                    params=params,
                    limit_id=CONSTANTS.TRADES_PATH_URL,
                    is_auth_required=False))

            self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):

                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    exchange_order_id = str(trade["orderId"])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=trade["baseCurrency"],
                            flat_fees=[TokenAmount(amount=Decimal(0), token=trade["baseCurrency"])]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["quantity"]),
                            fill_quote_amount=Decimal(trade["quantity"]),
                            fill_price=Decimal(trade["price"]),
                            fill_timestamp=trade["time"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                    elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
                        # This is a fill of an order registered in the DB but not tracked any more
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["id"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=float(trade["time"]) * 1e-3,
                                order_id=self._exchange_order_ids.get(str(trade["orderId"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                                order_type=OrderType.LIMIT_MAKER if trade["isMaker"] else OrderType.LIMIT,
                                price=Decimal(trade["price"]),
                                amount=Decimal(trade["quantity"]),
                                trade_fee=DeductedFromReturnsTradeFee(
                                    flat_fees=[
                                        TokenAmount(
                                            trade["baseCurrency"],
                                            Decimal(0)
                                        )
                                    ]
                                ),
                                exchange_trade_id=str(trade["id"])
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL,
                limit_id=CONSTANTS.TRADES_FOR_ORDER_PATH_URL)

            for trade in all_fills_response:
                exchange_order_id = str(trade["orderId"])
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["baseCurrency"],
                    flat_fees=[TokenAmount(amount=Decimal(0), token=trade["baseCurrency"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["quantity"]),
                    fill_quote_amount=Decimal(trade["quantity"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["time"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(f"{tracked_order.client_order_id}"),
        )

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data["time"] * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL.format(f"{CONSTANTS.CHAIN_ID}/{self.api_key}"),
            limit_id=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=False)

        balances = account_info
        for balance_entry in balances:
            asset_name = balance_entry["symbol"]
            free_balance = Decimal(balance_entry["balance"])
            total_balance = Decimal(balance_entry["balance"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

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

        return float(resp_json["ticker"]["price"])