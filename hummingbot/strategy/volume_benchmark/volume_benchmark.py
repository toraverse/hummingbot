import asyncio
import logging
from decimal import Decimal
from typing import Dict, List

import numpy as np

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent, SellOrderCompletedEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.strategy.utils import order_age

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("NaN")
vb_logger = None


class VolumeBenchmarkStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global vb_logger
        if vb_logger is None:
            vb_logger = logging.getLogger(__name__)
        return vb_logger

    def init_params(self,
                    market_info: MarketTradingPairTuple,
                    min_order_amount: Decimal,
                    max_order_amount: Decimal,
                    min_interval: float,
                    max_interval: float,
                    max_pending_orders: int,
                    max_order_age_buy: float = 1800.0,
                    max_order_age_sell: float = 1800.0,
                    order_price_interval_percentage: float = 80.0,
                    hb_app_notification: bool = False,
                    ):
        self._market_info = market_info
        self._min_order_amount = min_order_amount
        self._max_order_amount = max_order_amount
        self._min_interval = min_interval
        self._max_interval = max_interval
        self._max_pending_orders = max_pending_orders
        self._max_order_age_buy = max_order_age_buy
        self._max_order_age_sell = max_order_age_sell
        self._order_price_interval_percentage = order_price_interval_percentage
        self._hb_app_notification = hb_app_notification
        self._all_markets_ready = False

        self._order_placement_interval = 1.0
        self._order_amount = 1.0
        self._last_timestamp = 0
        self._current_timestamp = 1.0

        self.add_markets([market_info.market])

    def all_markets_ready(self):
        return all([market.ready for market in self.active_markets])

    @property
    def market_info(self) -> MarketTradingPairTuple:
        return self._market_info

    @property
    def min_order_amount(self) -> Decimal:
        return self._min_order_amount

    @min_order_amount.setter
    def min_order_amount(self, value: Decimal):
        self._min_order_amount = value

    @property
    def max_order_amount(self) -> Decimal:
        return self._max_order_amount

    @max_order_amount.setter
    def max_order_amount(self, value: Decimal):
        self._max_order_amount = value

    @property
    def min_interval(self) -> float:
        return self._min_interval

    @min_interval.setter
    def min_interval(self, value: float):
        self._min_interval = value

    @property
    def max_interval(self) -> float:
        return self._max_interval

    @max_interval.setter
    def max_interval(self, value: float):
        self._max_interval = value

    @property
    def max_pending_orders(self) -> int:
        return self._max_pending_orders

    @max_pending_orders.setter
    def max_pending_orders(self, value: int):
        self._max_pending_orders = value

    @property
    def max_order_age_buy(self) -> float:
        return self._max_order_age_buy

    @max_order_age_buy.setter
    def max_order_age_buy(self, value: float):
        self._max_order_age_buy = value

    @property
    def max_order_age_sell(self) -> float:
        return self._max_order_age_sell

    @max_order_age_sell.setter
    def max_order_age_sell(self, value: float):
        self._max_order_age_sell = value

    @property
    def order_price_interval_percentage(self) -> float:
        return self._order_price_interval_percentage

    @order_price_interval_percentage.setter
    def order_price_interval_percentage(self, value: float):
        self._order_price_interval_percentage = value

    @property
    def base_asset(self):
        return self.market_info.base_asset

    @property
    def quote_asset(self):
        return self.market_info.quote_asset

    @property
    def market(self) -> ExchangeBase:
        return self.market_info.market

    @property
    def trading_pair(self) -> str:
        return self.market_info.trading_pair

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self.order_tracker.market_pair_to_active_orders

    @property
    def active_orders(self) -> List[LimitOrder]:
        if self.market_info not in self.market_info_to_active_orders:
            return []
        return self.market_info_to_active_orders[self._market_info]

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        self._current_timestamp = timestamp
        last_tick = self._last_timestamp // self._order_placement_interval
        current_tick = self._current_timestamp // self._order_placement_interval

        self._all_markets_ready = self.all_markets_ready()
        if not self._all_markets_ready:
            # Markets not ready yet. Don't do anything.
            for market in self.active_markets:
                if not market.ready:
                    self.logger().warning(f"Market {market.name} is not ready.")
            self.logger().warning("Markets are not ready. Volume Benchmark strategy on hold.")
            return

        # Cancel orders that are older than max_order_age
        self.cancel_active_orders_on_max_age_limit()

        if current_tick > last_tick:
            if len(self.active_orders) > self.max_pending_orders:
                self.logger().warning(f"Max pending orders rcrossed: {len(self.active_orders)}. Will not place new orders until some orders are filled or cancelled.")
            else:
                safe_ensure_future(self.create_volume())

        self._last_timestamp = timestamp

    def cancel_active_orders_on_max_age_limit(self):
        """
        Cancel all active orders that are older than max_order_age
        """
        active_orders = self.active_orders

        for order in active_orders:
            if order.is_buy:
                if order_age(order, self._current_timestamp) > self.max_order_age_buy:
                    self.cancel_order(self.market_info, order.client_order_id)
            elif not order.is_buy:
                if order_age(order, self._current_timestamp) > self.max_order_age_sell:
                    self.cancel_order(self.market_info, order.client_order_id)

    async def create_volume(self):
        """
        Create volume by placing buy and sell orders at same price, while keeping the size and interval random.
        """
        # sample order_placement_interval from a uniform distribution of integers between min_interval and max_interval
        self._order_placement_interval = np.random.randint(int(self.min_interval), int(self.max_interval) + 1)
        # sample order_amount from a uniform distribution of floats between min_order_amount and max_order_amount
        self._order_amount = np.random.uniform(float(self.min_order_amount), float(self.max_order_amount))

        base_balance = self.market.get_available_balance(self.base_asset)
        quote_balance = self.market.get_available_balance(self.quote_asset)

        top_bid_price = self.market_info.get_price(False)
        top_ask_price = self.market_info.get_price(True)
        pad_price = (top_ask_price - top_bid_price) * ((Decimal("1.0") - (Decimal(str(self._order_price_interval_percentage)) / Decimal("100.0"))) / Decimal("2.0"))
        # the order price for both orders will be a price sampled uniformly from the
        # interval [top_bid_price + pad_price, top_ask_price - pad_price] - i.e, 80% of the spread in the middle
        order_price = np.random.uniform(float(top_bid_price + pad_price), float(top_ask_price - pad_price))
        # quantize the order price
        quantized_order_price = self.market.quantize_order_price(self.trading_pair, Decimal(str(order_price)))
        # quantize the order amount
        quantized_order_amount = self.market.quantize_order_amount(self.trading_pair, Decimal(str(self._order_amount)))
        required_quote_balance = quantized_order_amount * quantized_order_price

        self.logger().info(f"Creating BUY and SELL orders @ Price : {quantized_order_price}, Amount : {quantized_order_amount}, Interval : {self._order_placement_interval}")

        tasks = []
        # Only place orders if there are less than max_pending_orders pending orders, and if there is enough balance to place the order
        if base_balance > quantized_order_amount and quote_balance > required_quote_balance:
            tasks.append(self.place_order(True, quantized_order_amount, quantized_order_price))
            tasks.append(self.place_order(False, quantized_order_amount, quantized_order_price))
        else:
            self.logger().warning(f"Insufficient balance to place orders. Base balance: {base_balance}, Quote balance: {quote_balance}. \
                                  Required Base balance {quantized_order_amount}, Quote balance: {required_quote_balance}")

        # parallel way of placing orders
        await asyncio.gather(*tasks)

    async def place_order(self, is_buy: bool, amount: Decimal, price: Decimal) -> str:
        """
        Place a buy or sell order
        :param is_buy: True if buy order, False if sell order
        :param amount: Amount of base asset to buy or sell
        :param price: Price of the order
        :return: Order ID
        """
        order_fn = self.buy_with_specific_market if is_buy else self.sell_with_specific_market
        order_id = order_fn(self.market_info, amount, OrderType.LIMIT, price)

        return order_id

    def format_status(self) -> str:
        """
        Keeping it simple for now. Just return a string that says whether the strategy is running or not.
        """
        self._all_markets_ready = self.all_markets_ready()
        if not self._all_markets_ready:
            return "Markets are not ready. Volume Benchmark strategy on hold."
        else:
            return f"Volume Benchmark strategy is running. Current order placement interval is {self._order_placement_interval} seconds. Active orders: {len(self.active_orders)}"

    def start(self, clock: Clock, timestamp: float):
        self._last_timestamp = timestamp
        np.random.seed(int(timestamp))

    def stop(self, clock: Clock):
        pass

    def did_fill_order(self, event: OrderFilledEvent):
        self.logger().info(f"Your limit {event.trade_type.name} order {event.order_id} filled a trade.")
        self.logger().info(event)

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        self.logger().info(f"Your BUY order {event.order_id} has been completed.")
        self.logger().info(event)
        self.notify_hb_app_with_timestamp(f"BUY order {event.order_id} has been completed.")

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        self.logger().info(f"Your SELL order {event.order_id} has been completed.")
        self.logger().info(event)
        self.notify_hb_app_with_timestamp(f"SELL order {event.order_id} has been completed.")
