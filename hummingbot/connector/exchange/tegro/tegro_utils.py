import time
from decimal import Decimal
from typing import Any, Dict

from dateutil.parser import parse as dateparse
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS
from hummingbot.connector.exchange.tegro.tegro_tracking_nonce import get_tracking_nonce
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False
DOMAIN = ["tegro"]
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


def get_client_order_id(is_buy: bool) -> str:
    """
    Creates a client order id for a new order
    :param is_buy: True if the order is a buy order, False if the order is a sell order
    :return: an identifier for the new order to be used in the client
    """
    newId = str(get_tracking_nonce())[4:]
    side = "00" if is_buy else "01"
    return f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}{side}{newId}"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """

    return exchange_info.get("State", None) == "verified" and exchange_info['Symbol'].split('_')


def get_ms_timestamp() -> int:
    return int(_time() * 1e3)

# convert date string to timestampZ


def str_date_to_ts(date: str) -> int:
    return int(dateparse(date).timestamp())


class TegroConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="tegro", const=True, client_data=None)
    tegro_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Tegro API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    tegro_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Tegro API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "tegro"


KEYS = TegroConfigMap.construct()

OTHER_DOMAINS = ["tegro_testnet"]
OTHER_DOMAINS_PARAMETER = {"tegro_testnet": "tegro_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"tegro_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"tegro_testnet": DEFAULT_FEES}


class TegroTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="tegro_testnet", const=True, client_data=None)
    tegro_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your tegro public API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    tegro_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your tegro secret API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "tegro_testnet"


OTHER_DOMAINS_KEYS = {"tegro_testnet": TegroTestnetConfigMap.construct()}


def _time():
    """
    Private function created just to have a method that can be safely patched during unit tests and make tests
    independent from real time
    """
    return time.time()
