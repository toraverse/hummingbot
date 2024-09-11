from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ""

HBOT_ORDER_ID_PREFIX = "btse-"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://{}api.btse.com/spot/api/"
WSS_URL = "wss://{}ws.btse.com/ws/spot"
WSS_ORDER_BOOK_URL = "wss://{}ws.btse.com/ws/oss/spot"

PUBLIC_API_VERSION = "v3.2"
PRIVATE_API_VERSION = "v3.2"

# Public API endpoints or BtseClient function
TICKER_PRICE_CHANGE_PATH_URL = "/price"
TICKER_BOOK_PATH_URL = "/market_summary"
EXCHANGE_INFO_PATH_URL = "/market_summary"
PING_PATH_URL = "/time"
SNAPSHOT_PATH_URL = "/orderbook"
SERVER_TIME_PATH_URL = "/time"

# Private API endpoints or BtseClient function
ACCOUNTS_PATH_URL = "/user/wallet"
MY_TRADES_PATH_URL = "/user/trade_history"
ORDER_PATH_URL = "/order"
BTSE_USER_STREAM_CHANNEL = "authKeyExpires"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Btse params

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Order States
ORDER_STATE = {
    2: OrderState.OPEN,
    4: OrderState.FILLED,
    5: OrderState.PARTIALLY_FILLED,
    6: OrderState.CANCELED,
    7: OrderState.FAILED,
    8: OrderState.FAILED,
    15: OrderState.FAILED,
    16: OrderState.FAILED,
    17: OrderState.FAILED,
}

# Websocket event types
SNAPSHOT_EVENT_TYPE = "snapshot"
DIFF_EVENT_TYPE = "delta"
TRADE_EVENT_TYPE = "tradeHistoryApi"

# Rate Limits
RATE_LIMITS = [
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=15, time_interval=1),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=15, time_interval=1),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=15, time_interval=1),
    RateLimit(limit_id=PING_PATH_URL, limit=15, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=15, time_interval=1),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=15, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=75, time_interval=1),
    RateLimit(limit_id=ORDER_PATH_URL, limit=75, time_interval=1)
]

ORDER_NOT_EXIST_MESSAGE_OR_UNKNOWN = ["ORDER_NOTFOUND", "STATUS_PROCESSING", "STATUS_INACTIVE", "NOTFOUND", "doesn't exist"]
