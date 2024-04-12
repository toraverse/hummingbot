import logging
from decimal import Decimal
from typing import List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimplePMM(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Simple-PMM-63cc765486dd42228d3da0b32537fc92
    Video: -
    Description:
    The bot will place two orders around the price_source (mid price or last traded price) in a trading_pair on
    exchange, with a distance defined by the ask_spread and bid_spread. Every order_refresh_time in seconds,
    the bot will cancel and replace the orders.
    """
    bid_spread = 0.1
    ask_spread = 0.1
    order_refresh_time = 60
    order_amount = 12
    create_timestamp = 0
    trading_pair = "KRYPTONITE-USDT"
    exchange = "tegro"
    # Here you can use for example the LastTrade price to use in your strategy
    price_source = PriceType.MidPrice

    markets = {exchange: {trading_pair, "POKEBALLS-USDT"}}

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[OrderCandidate]:
        ref_price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        buy_price = ref_price * Decimal(1 - self.bid_spread)
        sell_price = ref_price * Decimal(1 + self.ask_spread)

        buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(self.order_amount), price=buy_price)

        sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(self.order_amount), price=sell_price)

        return [buy_order, sell_order]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        market_status_df = self.get_market_status_df_with_depth()
        lines.extend(["", "  Market Status Data Frame:"] + ["    " + line for line in market_status_df.to_string(index=False).split("\n")])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def get_market_status_df_with_depth(self):
        market_status_df = self.market_status_data_frame(self.get_market_trading_pair_tuples())
        market_status_df["Exchange"] = market_status_df.apply(lambda x: x["Exchange"], axis=1)
        market_status_df["Volume (+1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, 0.01), axis=1)
        market_status_df["Volume (-1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, -0.01), axis=1)
        return market_status_df

    def get_volume_for_percentage_from_mid_price(self, row, percentage):
        price = row["Mid Price"] * (1 + percentage)
        is_buy = percentage > 0
        result = self.connectors[row["Exchange"]].get_volume_for_price(row["Market"], is_buy, price)
        return result.result_volume
