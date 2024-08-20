"""
The configuration parameters for a user made volume_benchmark strategy.
"""

from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_validators import (
    validate_decimal,
    validate_exchange,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import AllConnectorSettings, required_exchanges


def exchange_on_validated(value: str) -> None:
    required_exchanges.add(value)


def trading_pair_prompt():
    exchange = volume_benchmark_config_map.get("exchange").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the trading pair you would like to provide volume for %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = volume_benchmark_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


def min_order_amount_prompt() -> str:
    trading_pair = volume_benchmark_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the minimum amount of {base_asset} per order? >>> "


def max_order_amount_prompt() -> str:
    trading_pair = volume_benchmark_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the maximum amount of {base_asset} per order? >>> "


def validate_max_order_amount(value: Decimal) -> Optional[str]:
    min_order_amount = volume_benchmark_config_map.get("min_order_amount").value

    return validate_decimal(value, min_value=Decimal(min_order_amount), inclusive=False)


def validate_max_interval(value: float) -> Optional[str]:
    min_interval = volume_benchmark_config_map.get("min_interval").value

    return validate_decimal(value, min_value=Decimal(min_interval), inclusive=False)


volume_benchmark_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="volume_benchmark"),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter the spot connector to use for volume benchmark strategy >>> ",
                  validator=validate_exchange,
                  on_validated=exchange_on_validated,
                  prompt_on_new=True),
    "market":
        ConfigVar(key="market",
                  prompt=trading_pair_prompt,
                  type_str="str",
                  validator=validate_exchange_trading_pair,
                  prompt_on_new=True),
    "min_order_amount":
        ConfigVar(key="min_order_amount",
                  prompt=min_order_amount_prompt,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  prompt_on_new=True),
    "max_order_amount":
        ConfigVar(key="max_order_amount",
                  prompt=max_order_amount_prompt,
                  type_str="decimal",
                  validator=validate_max_order_amount,
                  prompt_on_new=True),
    "min_interval":
        ConfigVar(key="min_interval",
                  prompt="What is the minimum time interval between orders in seconds >>> ",
                  type_str="float",
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
    "max_interval":
        ConfigVar(key="max_interval",
                  prompt="What is the maximum time interval between orders in seconds >>> ",
                  type_str="float",
                  validator=validate_max_interval,
                  prompt_on_new=True),
    "max_pending_orders":
        ConfigVar(key="max_pending_orders",
                  prompt="What is the maximum allowed pending volume making orders, till when new orders can be placed (1 indicates 1 BUY and 1 SELL) >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, min_value=1, inclusive=True),
                  prompt_on_new=True),
    "max_order_age_buy":
        ConfigVar(key="max_order_age_buy",
                  prompt="How long before you cancel the pending BUY orders (in seconds) >>> ",
                  type_str="float",
                  default=Decimal("1800"),
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
    "max_order_age_sell":
        ConfigVar(key="max_order_age_sell",
                  prompt="How long before you cancel the pending SELL orders (in seconds) >>> ",
                  type_str="float",
                  default=Decimal("1800"),
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
    "order_price_interval_percentage":
        ConfigVar(key="order_price_interval_percentage",
                  prompt="What is the price interval between top ask and top bid prices to place orders in?"
                  "(in percentage, 100 means total interval between top ask and top bid) >>> ",
                  type_str="float",
                  default=Decimal("80.0"),
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
}
