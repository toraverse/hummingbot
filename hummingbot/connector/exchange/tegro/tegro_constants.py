import sys

from hummingbot.connector.constants import SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "tegro"
DEFAULT_DOMAIN = "tegro"

DOMAIN = EXCHANGE_NAME
HBOT_ORDER_ID_PREFIX = "HB"
USER_AGENT = "HBOT"
MAX_ORDER_ID_LEN = 32

# Base URL
# https://api.testnet.tegro.com/v2

TEGRO_BASE_URL = "https://api.tegro.com/api/"
TESTNET_BASE_URL = "https://api.testnet.tegro.com/api/"
TEGRO_WS_URL = "wss://api.tegro.com/api/v1/events/"
TESTNET_WS_URL = "wss://events.testnet.tegro.com/"

CHAIN_ID = 8453

MAINNET_CHAIN_IDS = {
    "base": 8453,
}

ABI = {
    "approve": [
        {
            "name": "approve",
            "stateMutability": "nonpayable",
            "type": "function",
            "inputs": [{
                "internalType": "address",
                "name": "spender",
                "type": "address"
            }, {
                "internalType": "uint256",
                "name": "value",
                "type": "uint256"
            }],
            "outputs": [{
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }]
        },
    ],
    "allowance": [
        {
            "name": "allowance",
            "stateMutability": "view",
            "type": "function",
            "inputs": [{
                "internalType": "address",
                "name": "owner",
                "type": "address"
            }, {
                "internalType": "address",
                "name": "spender",
                "type": "address"
            }],
            "outputs": [{
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }]
        }
    ]
}

Node_URLS = {
    "arbitrum_sepolia": "https://sepolia-rollup.arbitrum.io/rpc",
    "polygon_amoy": "https://rpc-amoy.polygon.technology",
    "optimism_sepolia": "https://sepolia.optimism.io",
    "base_mainnet": "https://mainnet.base.org"
}

TESTNET_CHAIN_IDS = {
    "arbitrum": 42161,
    "polygon": 80002,
    "optimism": 11155420,
    "base": 8453
}

PUBLIC_WS_ENDPOINT = "ws"

# Public API endpoints or TegroClient function
TICKER_PRICE_CHANGE_PATH_URL = "v1/exchange/{}/market/{}"
EXCHANGE_INFO_PATH_LIST_URL = "v1/exchange/{}/market/list"
EXCHANGE_INFO_PATH_URL = "v1/exchange/{}/market/{}"
PING_PATH_URL = "v1/trading/health"  # TODO
SNAPSHOT_PATH_URL = "v1/trading/market/orderbook/depth"

# REST API ENDPOINTS
ACCOUNTS_PATH_URL = "v1/accounts/{}/{}/portfolio"
MARKET_LIST_PATH_URL = "v1/exchange/{}/market/list"
GENERATE_SIGN_URL = "v1/trading/market/orders/typedData/generate"
TRADES_PATH_URL = "v1/exchange/{}/market/trades"
TRADES_FOR_ORDER_PATH_URL = "v1/trading/market/orders/trades/{}"
ORDER_PATH_URL = "v1/trading/market/orders/place"
CHAIN_LIST = "v1/exchange/chain/list"
CHARTS_TRADES = "v1/exchange/{}/market/chart"
ORDER_LIST = "v1/trading/market/orders/user/{}"
CANCEL_ORDER_URL = "v1/trading/market/orders/cancel"
CANCEL_ORDER_ALL_URL = "v1/trading/market/orders/cancelAll"
TEGRO_USER_ORDER_PATH_URL = "v1/trading/market/orders/user/{}"


WS_HEARTBEAT_TIME_INTERVAL = 30

API_LIMIT_REACHED_ERROR_MESSAGE = "TOO MANY REQUESTS"

# Tegro params
SIDE_BUY = "buy"
SIDE_SELL = "sell"

ORDER_STATE = {
    "Pending": OrderState.FILLED,
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
        limit_id=CHAIN_LIST,
        limit=NO_LIMIT,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(TICKER_PRICE_CHANGE_PATH_URL)]
    ),
    RateLimit(
        limit_id=CHARTS_TRADES,
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
