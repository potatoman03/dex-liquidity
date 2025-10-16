"""
Orderbook state manager for tracking and processing orderbook updates
"""

from typing import Dict, Optional, List, Tuple
from collections import deque
from datetime import datetime
import asyncio
from loguru import logger

from .models import (
    OrderBookSnapshot,
    OrderBookLevel,
    LiquidityMetrics,
    PriceHistory,
    PricePoint,
)
from .liquidity_calculator import LiquidityCalculator, LIQUIDITY_SIZES
from .orderbook_cache import OrderbookCache


class OrderBookManager:
    """
    Manages orderbook state and liquidity calculations for multiple exchanges/markets
    """

    def __init__(self, price_history_seconds: int = 3600):
        """
        Initialize the orderbook manager

        Args:
            price_history_seconds: How much price history to keep (default 1 hour)
        """
        # Store orderbook caches: {(exchange, market): OrderbookCache}
        self._caches: Dict[Tuple[str, str], OrderbookCache] = {}

        # Store orderbook snapshots: {(exchange, market): OrderBookSnapshot}
        self._orderbooks: Dict[Tuple[str, str], OrderBookSnapshot] = {}

        # Store liquidity metrics: {(exchange, market): LiquidityMetrics}
        self._liquidity_metrics: Dict[Tuple[str, str], LiquidityMetrics] = {}

        # Store price history: {(exchange, market): deque[PricePoint]}
        self._price_history: Dict[Tuple[str, str], deque] = {}
        self._price_history_seconds = price_history_seconds

        # Locks for thread safety
        self._locks: Dict[Tuple[str, str], asyncio.Lock] = {}

        # Callback for immediate price updates
        self._price_update_callback = None

        logger.info(
            f"OrderBookManager initialized with {price_history_seconds}s price history"
        )

    def _get_key(self, exchange: str, market: str) -> Tuple[str, str]:
        """Get the storage key for an exchange/market pair"""
        return (exchange, market)

    def set_price_update_callback(self, callback):
        """
        Set callback for immediate price updates

        Args:
            callback: Async function(exchange, market, price, timestamp)
        """
        self._price_update_callback = callback

    async def _get_lock(self, exchange: str, market: str) -> asyncio.Lock:
        """Get or create a lock for an exchange/market pair"""
        key = self._get_key(exchange, market)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _get_or_create_cache(self, exchange: str, market: str) -> OrderbookCache:
        """Get or create orderbook cache for exchange/market pair"""
        key = self._get_key(exchange, market)
        if key not in self._caches:
            self._caches[key] = OrderbookCache(exchange, market)
        return self._caches[key]

    async def initialize_orderbook(
        self,
        exchange: str,
        market: str,
        bids: List[OrderBookLevel],
        asks: List[OrderBookLevel],
        timestamp: Optional[float] = None,
    ) -> bool:
        """
        Initialize orderbook cache with full snapshot (from REST API)

        Args:
            exchange: Exchange name ("hyperliquid" or "lighter")
            market: Market symbol
            bids: List of bid levels
            asks: List of ask levels
            timestamp: Snapshot timestamp (defaults to current time)

        Returns:
            True if initialization was successful
        """
        if timestamp is None:
            timestamp = datetime.now().timestamp()

        lock = await self._get_lock(exchange, market)

        async with lock:
            try:
                # Get or create cache
                cache = self._get_or_create_cache(exchange, market)

                # Initialize cache
                cache.initialize(bids, asks, timestamp)

                # Generate snapshot from cache
                await self._update_from_cache(exchange, market, timestamp)

                return True

            except Exception as e:
                logger.error(f"Error initializing {exchange} {market} orderbook: {e}")
                return False

    async def update_orderbook(
        self,
        exchange: str,
        market: str,
        bids: List[OrderBookLevel],
        asks: List[OrderBookLevel],
        timestamp: Optional[float] = None,
        is_snapshot: bool = False,
    ) -> bool:
        """
        Apply incremental update to orderbook cache (from WebSocket)

        Args:
            exchange: Exchange name ("hyperliquid" or "lighter")
            market: Market symbol
            bids: List of bid level updates
            asks: List of ask level updates
            timestamp: Update timestamp (defaults to current time)
            is_snapshot: If True, treats as full snapshot (initializes cache)

        Returns:
            True if update was successful
        """
        if timestamp is None:
            timestamp = datetime.now().timestamp()

        lock = await self._get_lock(exchange, market)

        async with lock:
            try:
                # Get or create cache
                cache = self._get_or_create_cache(exchange, market)

                if is_snapshot or not cache.is_initialized():
                    # Initialize cache with snapshot
                    cache.initialize(bids, asks, timestamp)
                else:
                    # Apply incremental update
                    cache.update(bids, asks, timestamp)

                # Generate snapshot from cache
                await self._update_from_cache(exchange, market, timestamp)

                return True

            except Exception as e:
                logger.error(f"Error updating {exchange} {market} orderbook: {e}")
                return False

    async def _update_from_cache(self, exchange: str, market: str, timestamp: float):
        """Generate orderbook snapshot and metrics from cache"""
        key = self._get_key(exchange, market)
        cache = self._caches.get(key)

        if not cache or not cache.has_valid_book():
            logger.warning(f"Cannot update from invalid cache: {exchange} {market}")
            return

        # Get sorted levels from cache
        bids, asks = cache.get_sorted_levels()

        # Create snapshot
        snapshot = OrderBookSnapshot(
            exchange=exchange,
            market=market,
            bids=bids,
            asks=asks,
            timestamp=timestamp,
        )

        # Store snapshot
        self._orderbooks[key] = snapshot

        # Update price history
        mid_price = snapshot.mid_price
        if mid_price is not None:
            self._update_price_history(exchange, market, mid_price, timestamp)

            # Send immediate price update callback (tick-level)
            if self._price_update_callback:
                asyncio.create_task(
                    self._price_update_callback(exchange, market, mid_price, timestamp)
                )

        # Calculate liquidity metrics
        metrics = LiquidityCalculator.calculate_all_metrics(snapshot)
        self._liquidity_metrics[key] = metrics

        logger.debug(
            f"Updated {exchange} {market} from cache: "
            f"{len(bids)} bids, {len(asks)} asks, "
            f"mid=${(mid_price if mid_price is not None else 0):.2f}"
        )

    def _update_price_history(
        self, exchange: str, market: str, price: float, timestamp: float
    ):
        """Update price history and prune old data"""
        key = self._get_key(exchange, market)

        if key not in self._price_history:
            self._price_history[key] = deque()

        history = self._price_history[key]

        # Add new price point
        history.append(PricePoint(timestamp=timestamp, price=price))

        # Remove old data points
        cutoff_time = timestamp - self._price_history_seconds
        while history and history[0].timestamp < cutoff_time:
            history.popleft()

    async def get_orderbook(
        self, exchange: str, market: str
    ) -> Optional[OrderBookSnapshot]:
        """
        Get current orderbook snapshot

        Args:
            exchange: Exchange name
            market: Market symbol

        Returns:
            OrderBookSnapshot or None if not available
        """
        key = self._get_key(exchange, market)
        lock = await self._get_lock(exchange, market)

        async with lock:
            return self._orderbooks.get(key)

    async def get_liquidity_metrics(
        self, exchange: str, market: str
    ) -> Optional[LiquidityMetrics]:
        """
        Get current liquidity metrics

        Args:
            exchange: Exchange name
            market: Market symbol

        Returns:
            LiquidityMetrics or None if not available
        """
        key = self._get_key(exchange, market)
        lock = await self._get_lock(exchange, market)

        async with lock:
            return self._liquidity_metrics.get(key)

    async def get_price_history(
        self, exchange: str, market: str, duration_seconds: Optional[int] = None
    ) -> Optional[PriceHistory]:
        """
        Get price history for charting

        Args:
            exchange: Exchange name
            market: Market symbol
            duration_seconds: How much history to return (defaults to all available)

        Returns:
            PriceHistory or None if not available
        """
        key = self._get_key(exchange, market)
        lock = await self._get_lock(exchange, market)

        async with lock:
            if key not in self._price_history:
                return None

            history = self._price_history[key]
            if not history:
                return None

            # Filter by duration if specified
            if duration_seconds is not None:
                latest_timestamp = history[-1].timestamp
                cutoff_time = latest_timestamp - duration_seconds
                data_points = [p for p in history if p.timestamp >= cutoff_time]
            else:
                data_points = list(history)

            return PriceHistory(
                exchange=exchange,
                market=market,
                data_points=data_points,
                timeframe_seconds=duration_seconds or self._price_history_seconds,
            )

    async def get_all_orderbooks(self) -> List[OrderBookSnapshot]:
        """
        Get all current orderbook snapshots

        Returns:
            List of all orderbook snapshots
        """
        snapshots = []
        for key in list(self._orderbooks.keys()):
            exchange, market = key
            snapshot = await self.get_orderbook(exchange, market)
            if snapshot:
                snapshots.append(snapshot)
        return snapshots

    async def get_all_markets(self) -> List[Tuple[str, str]]:
        """
        Get all tracked exchange/market pairs

        Returns:
            List of (exchange, market) tuples
        """
        return list(self._orderbooks.keys())

    def get_stats(self) -> Dict[str, int]:
        """
        Get manager statistics

        Returns:
            Dict with counts of tracked markets and data points
        """
        total_price_points = sum(len(h) for h in self._price_history.values())

        return {
            "tracked_markets": len(self._orderbooks),
            "total_price_points": total_price_points,
            "price_history_seconds": self._price_history_seconds,
        }

    async def clear(self):
        """Clear all stored data"""
        async with asyncio.Lock():
            self._orderbooks.clear()
            self._liquidity_metrics.clear()
            self._price_history.clear()
            self._locks.clear()
            logger.info("OrderBookManager cleared")
