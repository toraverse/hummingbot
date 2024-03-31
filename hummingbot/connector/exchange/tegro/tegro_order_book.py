from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class TegroOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)

        trading_pair = msg.get("trading_pair", "")
        time = msg.get("timestamp", "")
        bids = cls.parse_entries(msg.get("Bids", []))
        asks = cls.parse_entries(msg.get("Asks", []))

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": time,
            "bids": bids,
            "asks": asks,
        }, timestamp=timestamp)

    @staticmethod
    def parse_entries(entries: list) -> list:
        parsed_entries = []
        if entries is not None:
            for entry in entries:
                price = Decimal(entry.get('price_float', 0))
                quantity = Decimal(entry.get('quantity_float', 0))
                if price is not None and quantity is not None:
                    parsed_entry = [float(price), float(quantity)]
                    parsed_entries.append(parsed_entry)
        return parsed_entries

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "update_id": msg["data"]["timestamp"],
            "bids": [[float(entry['price_float']), entry['quantity_float']] for entry in msg["data"]["bids"]],
            "asks": [[float(entry['price_float']), entry['quantity_float']] for entry in msg["data"]["asks"]],
        }, timestamp=timestamp * 1e-3)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None, metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = timestamp
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["data"]["symbol"],
            "trade_type": float(TradeType.SELL.value) if msg["data"]["takerType"] == "sell" else float(TradeType.BUY.value),
            "trade_id": msg["data"]["id"],
            "update_id": ts,
            "price": msg["data"]["price"],
            "amount": msg["data"]["amount"]
        }, timestamp=ts * 1e-3)
