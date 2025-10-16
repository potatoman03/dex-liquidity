"""
Hyperliquid WebSocket API Wrapper
"""

from .client import HyperliquidWebSocket
from .types import WsBook, WsLevel, OrderBookUpdate, SubscriptionType

__all__ = [
    "HyperliquidWebSocket",
    "WsBook",
    "WsLevel",
    "OrderBookUpdate",
    "SubscriptionType",
]

__version__ = "1.0.0"
