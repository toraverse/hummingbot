from typing import List, Tuple

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.volume_benchmark import VolumeBenchmarkStrategy
from hummingbot.strategy.volume_benchmark.volume_benchmark_config_map import volume_benchmark_config_map as c_map


def start(self):
    try:
        exchange = c_map.get("exchange").value.lower()
        raw_trading_pair = c_map.get("market").value
        min_order_amount = c_map.get("min_order_amount").value
        max_order_amount = c_map.get("max_order_amount").value
        min_interval = c_map.get("min_interval").value
        max_interval = c_map.get("max_interval").value
        max_pending_orders = c_map.get("max_pending_orders").value
        max_order_age_buy = c_map.get("max_order_age_buy").value
        max_order_age_sell = c_map.get("max_order_age_sell").value
        order_price_interval_percentage = c_map.get("order_price_interval_percentage").value

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        self.strategy = VolumeBenchmarkStrategy()
        self.strategy.init_params(
            market_info=MarketTradingPairTuple(*maker_data),
            min_order_amount=min_order_amount,
            max_order_amount=max_order_amount,
            min_interval=min_interval,
            max_interval=max_interval,
            max_pending_orders=max_pending_orders,
            max_order_age_buy=max_order_age_buy,
            max_order_age_sell=max_order_age_sell,
            order_price_interval_percentage=order_price_interval_percentage,
            hb_app_notification=True,
        )
    except Exception as e:
        self.notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
