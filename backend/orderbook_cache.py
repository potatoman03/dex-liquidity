"""
Orderbook cache for maintaining full orderbook state
"""

from typing import Dict, List, Tuple
from collections import OrderedDict
from loguru import logger

from .models import OrderBookLevel


class OrderbookCache:
    """
    Maintains full orderbook state with incremental updates

    Stores bids and asks as price -> size dictionaries
    Applies WebSocket incremental updates
    Can be initialized from REST API snapshot
    """

    def __init__(self, exchange: str, market: str):
        """
        Initialize orderbook cache

        Args:
            exchange: Exchange name
            market: Market symbol
        """
        self.exchange = exchange
        self.market = market

        # Store as price -> size dictionaries for fast updates
        self._bids: Dict[float, float] = {}  # price -> size
        self._asks: Dict[float, float] = {}  # price -> size

        self._last_update_timestamp = 0.0
        self._initialized = False

    def initialize(self, bids: List[OrderBookLevel], asks: List[OrderBookLevel], timestamp: float):
        """
        Initialize cache with full orderbook snapshot (from REST API)

        Args:
            bids: List of bid levels
            asks: List of ask levels
            timestamp: Snapshot timestamp
        """
        self._bids.clear()
        self._asks.clear()

        for level in bids:
            self._bids[level.price] = level.size

        for level in asks:
            self._asks[level.price] = level.size

        self._last_update_timestamp = timestamp
        self._initialized = True

        logger.debug(
            f"Initialized {self.exchange} {self.market} cache with "
            f"{len(self._bids)} bids, {len(self._asks)} asks"
        )

    def update(self, bids: List[OrderBookLevel], asks: List[OrderBookLevel], timestamp: float):
        """
        Apply incremental update to cache (from WebSocket)

        If size is 0, removes the level. Otherwise, updates/adds the level.

        Args:
            bids: Bid level updates
            asks: Ask level updates
            timestamp: Update timestamp
        """
        if not self._initialized:
            logger.warning(
                f"Applying update to uninitialized {self.exchange} {self.market} cache"
            )
            # Treat as initialization if not initialized
            self.initialize(bids, asks, timestamp)
            return

        # Apply bid updates
        for level in bids:
            if level.size <= 0:
                # Remove level
                self._bids.pop(level.price, None)
            else:
                # Update/add level
                self._bids[level.price] = level.size

        # Apply ask updates
        for level in asks:
            if level.size <= 0:
                # Remove level
                self._asks.pop(level.price, None)
            else:
                # Update/add level
                self._asks[level.price] = level.size

        self._last_update_timestamp = timestamp

        logger.debug(
            f"Updated {self.exchange} {self.market} cache: "
            f"{len(bids)} bid updates, {len(asks)} ask updates. "
            f"Total: {len(self._bids)} bids, {len(self._asks)} asks"
        )

    def get_sorted_levels(self, limit: int = None) -> Tuple[List[OrderBookLevel], List[OrderBookLevel]]:
        """
        Get sorted bid and ask levels

        Args:
            limit: Optional limit on number of levels to return

        Returns:
            Tuple of (bids, asks) as OrderBookLevel lists
            Bids are sorted descending (best first)
            Asks are sorted ascending (best first)
        """
        # Sort bids descending (highest price first)
        sorted_bids = sorted(self._bids.items(), key=lambda x: x[0], reverse=True)
        if limit:
            sorted_bids = sorted_bids[:limit]

        # Sort asks ascending (lowest price first)
        sorted_asks = sorted(self._asks.items(), key=lambda x: x[0])
        if limit:
            sorted_asks = sorted_asks[:limit]

        bids = [OrderBookLevel(price=price, size=size) for price, size in sorted_bids]
        asks = [OrderBookLevel(price=price, size=size) for price, size in sorted_asks]

        return bids, asks

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        bids, asks = self.get_sorted_levels(limit=1)

        best_bid = bids[0].price if bids else None
        best_ask = asks[0].price if asks else None

        mid_price = None
        spread = None
        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid

        return {
            "exchange": self.exchange,
            "market": self.market,
            "bid_levels": len(self._bids),
            "ask_levels": len(self._asks),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": mid_price,
            "spread": spread,
            "initialized": self._initialized,
            "last_update": self._last_update_timestamp,
        }

    def is_initialized(self) -> bool:
        """Check if cache has been initialized"""
        return self._initialized

    def has_valid_book(self) -> bool:
        """Check if cache has valid orderbook data"""
        return self._initialized and len(self._bids) > 0 and len(self._asks) > 0
