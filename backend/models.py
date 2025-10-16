"""
Data models for the orderbook aggregation backend
"""

from typing import List, Dict, Optional, Literal, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


class OrderBookLevel(BaseModel):
    """Single orderbook level"""
    price: float
    size: float

    class Config:
        json_schema_extra = {
            "example": {
                "price": 110890.0,
                "size": 33.2075
            }
        }


class OrderBookSnapshot(BaseModel):
    """Complete orderbook snapshot"""
    exchange: Literal["hyperliquid", "lighter"]
    market: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: float

    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price"""
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Calculate spread"""
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        """Calculate spread in basis points"""
        if self.mid_price and self.spread:
            return (self.spread / self.mid_price) * 10000
        return None


class LiquidityMetric(BaseModel):
    """Liquidity metric for a specific size"""
    size_usd: float
    total_cost: float  # Total cost including slippage
    avg_price: float   # Volume-weighted average price
    slippage_bps: float  # Slippage in basis points
    levels_used: int   # Number of levels crossed
    feasible: bool     # Whether enough liquidity exists


class LiquidityMetricPair(BaseModel):
    """Buy and sell liquidity metrics for a specific size"""
    buy: LiquidityMetric
    sell: LiquidityMetric

    class Config:
        # Allow arbitrary types for backward compatibility
        arbitrary_types_allowed = True


class LiquidityMetrics(BaseModel):
    """Liquidity metrics at various sizes"""
    exchange: Literal["hyperliquid", "lighter"]
    market: str
    timestamp: float
    metrics: Dict[str, Any]  # Key is size (e.g., "1000", "5000"), value is LiquidityMetricPair or dict

    class Config:
        # Allow arbitrary types for flexibility
        arbitrary_types_allowed = True


class PricePoint(BaseModel):
    """Single price point for charting"""
    timestamp: float
    price: float


class PriceHistory(BaseModel):
    """Price history for charting"""
    exchange: Literal["hyperliquid", "lighter"]
    market: str
    data_points: List[PricePoint]
    timeframe_seconds: int  # How much history is included


class OrderBookUpdate(BaseModel):
    """WebSocket message for orderbook update"""
    type: Literal["orderbook_update"] = "orderbook_update"
    exchange: Literal["hyperliquid", "lighter"]
    market: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    mid: Optional[float]
    spread: Optional[float]
    spread_bps: Optional[float]
    timestamp: float


class LiquidityMetricsUpdate(BaseModel):
    """WebSocket message for liquidity metrics update"""
    type: Literal["liquidity_metrics"] = "liquidity_metrics"
    exchange: Literal["hyperliquid", "lighter"]
    market: str
    metrics: Dict[str, Dict[str, float]]  # Simplified for frontend
    timestamp: float


class PriceUpdate(BaseModel):
    """WebSocket message for price update"""
    type: Literal["price_update"] = "price_update"
    exchange: Literal["hyperliquid", "lighter"]
    market: str
    price: float
    timestamp: float


class SubscriptionMessage(BaseModel):
    """Client subscription message"""
    action: Literal["subscribe", "unsubscribe"]
    markets: List[str]  # e.g., ["BTC", "ETH"]


class ConnectionStats(BaseModel):
    """Connection statistics"""
    exchange: Literal["hyperliquid", "lighter"]
    connected: bool
    last_update: Optional[float]
    messages_received: int
    errors: int
