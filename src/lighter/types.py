"""
Type definitions for Lighter WebSocket API
"""

from dataclasses import dataclass
from typing import List, Tuple, Callable, Optional


@dataclass
class OrderBookLevel:
    """
    Represents a single level in the order book

    Attributes:
        price: Price level as string
        size: Size at this level as string
    """
    price: str
    size: str

    @classmethod
    def from_dict(cls, data: dict) -> 'OrderBookLevel':
        """Create OrderBookLevel from API response"""
        return cls(price=data['price'], size=data['size'])


@dataclass
class OrderBook:
    """
    Order book snapshot for Lighter

    Attributes:
        code: Status code
        asks: List of ask levels
        bids: List of bid levels
        offset: Message offset/sequence number
        market_index: Market identifier
        channel: Channel name
        type: Message type
    """
    code: int
    asks: List[OrderBookLevel]
    bids: List[OrderBookLevel]
    offset: int
    market_index: int
    channel: str
    type: str

    @classmethod
    def from_dict(cls, data: dict) -> 'OrderBook':
        """Create OrderBook from API response"""
        try:
            order_book_data = data['order_book']
            asks = [OrderBookLevel.from_dict(level) for level in order_book_data['asks']]
            bids = [OrderBookLevel.from_dict(level) for level in order_book_data['bids']]

            # Extract market_index from channel string (e.g., "order_book:0" -> 0)
            channel = data['channel']
            market_index = int(channel.split(':')[1]) if ':' in channel else 0

            return cls(
                code=order_book_data['code'],
                asks=asks,
                bids=bids,
                offset=order_book_data['offset'],
                market_index=market_index,
                channel=channel,
                type=data['type']
            )
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise ValueError(f"Failed to parse OrderBook data: {e}. Data: {data}")

    def get_best_bid(self) -> Optional[OrderBookLevel]:
        """Get the best bid (highest price)"""
        return self.bids[0] if self.bids else None

    def get_best_ask(self) -> Optional[OrderBookLevel]:
        """Get the best ask (lowest price)"""
        return self.asks[0] if self.asks else None

    def get_spread(self) -> Optional[float]:
        """Calculate the spread between best bid and ask"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return float(best_ask.price) - float(best_bid.price)
        return None

    def get_mid_price(self) -> Optional[float]:
        """Calculate the mid price between best bid and ask"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (float(best_bid.price) + float(best_ask.price)) / 2
        return None


@dataclass
class OrderBookUpdate:
    """
    Order book update message wrapper

    Attributes:
        channel: The channel type
        data: The order book data
    """
    channel: str
    data: OrderBook


# Type aliases for callbacks
OrderBookCallback = Callable[[OrderBook], None]
MessageCallback = Callable[[dict], None]
ErrorCallback = Callable[[Exception], None]
