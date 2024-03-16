import sys

from hummingbot.connector.constants import SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "tegro"

DOMAIN = EXCHANGE_NAME
HBOT_ORDER_ID_PREFIX = "HB"
USER_AGENT = "HBOT"
MAX_ORDER_ID_LEN = 32

# Base URL
# https://api.testnet.tegro.com/v2

TEGRO_BASE_URL = "https://api.testnet.tegro.com/v2/"
TESTNET_BASE_URL = "https://api.testnet.tegro.com/v2/"
TEGRO_WS_URL = "wss://events.testnet.tegro.com/"
TESTNET_WS_URL = "wss://events.testnet.tegro.com/"

CHAIN_ID = 80001

PUBLIC_WS_ENDPOINT = "ws"

# Public API endpoints or TegroClient function
TICKER_PRICE_CHANGE_PATH_URL = "market"
EXCHANGE_INFO_PATH_LIST_URL = "market/list"
EXCHANGE_INFO_PATH_URL = "market"
PING_PATH_URL = "market/list"  # TODO
SNAPSHOT_PATH_URL = "market/orderbook/depth"

# REST API ENDPOINTS
ACCOUNTS_PATH_URL = "wallet/balances/{}"
MARKET_LIST_PATH_URL = "market/list"
GENERATE_SIGN_URL = "market/orders/typedData/generate/v2"
TRADES_PATH_URL = "market/trades"
TRADES_FOR_ORDER_PATH_URL = "market/orders/trades/{}"
ORDER_PATH_URL = "market/orders"
ORDER_LIST = "market/orders/user/{}"
CANCEL_ORDER_URL = "market/orders/cancel"
CANCEL_ORDER_ALL_URL = "market/orders/cancelAll"
TEGRO_USER_ORDER_PATH_URL = "market/orders/user/{}"


WS_HEARTBEAT_TIME_INTERVAL = 30

# Tegro params

SIDE_BUY = "buy"
SIDE_SELL = "sell"

ORDER_STATE = {
    "Pending": OrderState.PENDING_CREATE,
    "Active": OrderState.OPEN,
    "Matched": OrderState.FILLED,
    "Completed": OrderState.COMPLETED,
    "SoftCancelled": OrderState.PENDING_CANCEL,
    "Cancelled": OrderState.CANCELED,
}

TRADE_EVENT_TYPE = "trade_updated"
DIFF_EVENT_TYPE = "order_book_diff"

WS_METHODS = {
    "ORDER_PLACED": "order_placed",
    "ORDER_SUBMITTED": "order_submitted",
    "ORDER_BOOK_UPDATE": "order_book_updated",
    "ORDER_BOOK_UPDATE_DIFF": "order_book_diff",
    "TRADES_CREATE": "trade_created",
    "TRADES_UPDATE": "trade_updated",
    "ORDER_SUBMITTED_ONCHAIN": "order_submitted_onchain",
}

USER_METHODS = {
    "ORDER_PLACED": "order_placed",
    "ORDER_SUBMITTED": "order_submitted",
    "TRADES_CREATE": "user_trade_created",
    "TRADES_UPDATE": "user_trade_updated",
    "ORDER_SUBMITTED_ONCHAIN": "order_submitted_onchain",
}

HEARTBEAT_TIME_INTERVAL = 30.0

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    # Weighted Limits
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_LIST_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=TEGRO_USER_ORDER_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=TRADES_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=ORDER_LIST,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=MARKET_LIST_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=GENERATE_SIGN_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=TRADES_FOR_ORDER_PATH_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_ALL_URL,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)
                       ])
]


ORDER_NOT_EXIST_ERROR_CODE = -2013
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = -2011
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"
