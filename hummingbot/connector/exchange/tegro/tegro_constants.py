import sys

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "tegro"

DOMAIN = EXCHANGE_NAME
HBOT_ORDER_ID_PREFIX = "HB"

MAX_ORDER_ID_LEN = 32

# Base URL
# https://api.testnet.tegro.com/v2/market/orders

TEGRO_BASE_URL = "https://api.testnet.tegro.com/v2/"
TESTNET_BASE_URL = "https://api.testnet.tegro.com/v2/"
TEGRO_WS_URL = "wss://api.testnet.tegro.com/v2/ws"
TESTNET_WS_URL = "wss://api.testnet.tegro.com/v2/ws"

CHAIN_ID = 80001

# Public API endpoints or TegroClient function
TICKER_PRICE_CHANGE_PATH_URL = "market"
TICKER_BOOK_PATH_URL = "market/list"
EXCHANGE_INFO_PATH_URL = "market"
PING_PATH_URL = "chain/list"
SNAPSHOT_PATH_URL = "market/orderbook/depth"

# REST API ENDPOINTS
ACCOUNTS_PATH_URL = "wallet/balances/{}"
MARKET_LIST_PATH_URL = "market/list"
GENERATE_SIGN_URL = "market/orders/typedData/generate"
TRADES_PATH_URL = "market/trades"
TRADES_FOR_ORDER_PATH_URL = "market/orders/trades/{}"
ORDER_PATH_URL = "market/orders"
USER_ORDER_PATH_URL = "market/orders/user"
CANCEL_ORFDER_URL = "market/orders/cancel"
CANCEL_ORDER_ALL_URL = "market/orders/cancelAll"
TEGRO_USER_ORDER_PATH_URL = "market/orders/user/{}"


WS_HEARTBEAT_TIME_INTERVAL = 30

# Tegro params

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

ORDER_STATE = {
    "Active": OrderState.OPEN,
    "Matched": OrderState.FILLED,
    "SoftCancelled": OrderState.PARTIALLY_FILLED,
    "Canceled": OrderState.CANCELED,
}

WS_ORDER = "order"
WS_TRADE = "trade"

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

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=6000, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=50, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=160000, time_interval=ONE_DAY),
    RateLimit(limit_id=RAW_REQUESTS, limit=61000, time_interval= 5 * ONE_MINUTE),
    # Weighted Limits
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 100),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=TEGRO_USER_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)])
]


ORDER_NOT_EXIST_ERROR_CODE = -2013
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = -2011
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"
