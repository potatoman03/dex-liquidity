"""
Type definitions for Hyperliquid WebSocket API
"""

from dataclasses import dataclass
from typing import List, Tuple, Callable, Any, Optional
from enum import Enum


class SubscriptionType(Enum):
    """Available subscription types"""
    L2_BOOK = "l2Book"
    TRADES = "trades"
    USER_EVENTS = "userEvents"
    ALL_MIDS = "allMids"


@dataclass
class WsLevel:
    """
    Represents a single level in the order book

    Attributes:
        px: Price level as string
        sz: Size at this level as string
        n: Number of orders at this level
    """
    px: str  # price
    sz: str  # size
    n: int   # number of orders

    @classmethod
    def from_dict(cls, data) -> 'WsLevel':
        """Create WsLevel from API response (dict or list [px, sz, n])"""
        if isinstance(data, dict):
            return cls(px=data['px'], sz=data['sz'], n=data['n'])
        elif isinstance(data, (list, tuple)):
            return cls(px=data[0], sz=data[1], n=data[2])
        else:
            raise ValueError(f"Unexpected data format for WsLevel: {type(data)}")


@dataclass
class WsBook:
    """
    Order book snapshot

    Attributes:
        coin: Trading pair symbol (e.g., "BTC")
        levels: Tuple of (bids, asks) where each is a list of WsLevel
        time: Timestamp in milliseconds
    """
    coin: str
    levels: Tuple[List[WsLevel], List[WsLevel]]  # (bids, asks)
    time: int

    @classmethod
    def from_dict(cls, data: dict) -> 'WsBook':
        """Create WsBook from API response"""
        try:
            bids = [WsLevel.from_dict(level) for level in data['levels'][0]]
            asks = [WsLevel.from_dict(level) for level in data['levels'][1]]
            return cls(
                coin=data['coin'],
                levels=(bids, asks),
                time=data['time']
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"Failed to parse WsBook data: {e}. Data: {data}")

    @property
    def bids(self) -> List[WsLevel]:
        """Get bid levels"""
        return self.levels[0]

    @property
    def asks(self) -> List[WsLevel]:
        """Get ask levels"""
        return self.levels[1]

    def get_best_bid(self) -> Optional[WsLevel]:
        """Get the best bid (highest price)"""
        return self.bids[0] if self.bids else None

    def get_best_ask(self) -> Optional[WsLevel]:
        """Get the best ask (lowest price)"""
        return self.asks[0] if self.asks else None

    def get_spread(self) -> Optional[float]:
        """Calculate the spread between best bid and ask"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return float(best_ask.px) - float(best_bid.px)
        return None


@dataclass
class OrderBookUpdate:
    """
    Order book update message wrapper

    Attributes:
        channel: The channel type (e.g., "l2Book")
        data: The order book data
    """
    channel: str
    data: WsBook


# Type aliases for callbacks
OrderBookCallback = Callable[[WsBook], None]
MessageCallback = Callable[[dict], None]
ErrorCallback = Callable[[Exception], None]
