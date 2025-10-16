"""
WebSocket connection manager for DEX exchanges
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

from loguru import logger

# Add src directory to path to import exchange clients
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from hyperliquid import HyperliquidWebSocket, WsBook
from lighter import LighterWebSocket
from lighter import OrderBook as LighterOrderBook

from .lighter_rest_client import LighterRestClient
from .models import ConnectionStats, OrderBookLevel
from .orderbook_manager import OrderBookManager


class ConnectionManager:
    """
    Manages WebSocket connections to multiple DEX exchanges
    """

    def __init__(self, orderbook_manager: OrderBookManager):
        """
        Initialize connection manager

        Args:
            orderbook_manager: OrderBookManager instance to forward updates to
        """
        self.orderbook_manager = orderbook_manager

        # Exchange clients
        self.hyperliquid_client: Optional[HyperliquidWebSocket] = None
        self.lighter_client: Optional[LighterWebSocket] = None
        self.lighter_rest_client: Optional[LighterRestClient] = None

        # Track subscriptions
        self.hyperliquid_subscriptions: Set[str] = set()
        self.lighter_subscriptions: Set[int] = set()

        # Background tasks
        self._rest_fetch_task: Optional[asyncio.Task] = None
        self._should_stop = False

        # Connection stats
        self.hyperliquid_stats = {
            "connected": False,
            "last_update": None,
            "messages_received": 0,
            "errors": 0,
        }
        self.lighter_stats = {
            "connected": False,
            "last_update": None,
            "messages_received": 0,
            "errors": 0,
        }

        logger.info("ConnectionManager initialized")

    async def start(self):
        """Start connections to all exchanges"""
        await asyncio.gather(
            self._start_hyperliquid(), self._start_lighter(), self._start_lighter_rest()
        )

        # Start periodic REST fetch task
        self._rest_fetch_task = asyncio.create_task(self._periodic_rest_fetch())

        logger.success("All exchange connections started")

    async def _start_hyperliquid(self):
        """Start Hyperliquid WebSocket connection"""
        try:
            self.hyperliquid_client = HyperliquidWebSocket(auto_reconnect=True)
            await self.hyperliquid_client.connect()
            self.hyperliquid_stats["connected"] = True
            logger.success("Connected to Hyperliquid")
        except Exception as e:
            logger.error(f"Failed to connect to Hyperliquid: {e}")
            self.hyperliquid_stats["errors"] += 1

    async def _start_lighter(self):
        """Start Lighter WebSocket connection"""
        try:
            self.lighter_client = LighterWebSocket(testnet=False, auto_reconnect=True)
            await self.lighter_client.connect()
            self.lighter_stats["connected"] = True
            logger.success("Connected to Lighter WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to Lighter WebSocket: {e}")
            self.lighter_stats["errors"] += 1

    async def _start_lighter_rest(self):
        """Start Lighter REST client"""
        try:
            self.lighter_rest_client = LighterRestClient(testnet=False)
            await self.lighter_rest_client.connect()
            logger.success("Connected to Lighter REST API")
        except Exception as e:
            logger.error(f"Failed to connect to Lighter REST API: {e}")
            self.lighter_stats["errors"] += 1

    async def subscribe_hyperliquid(self, coin: str, n_levels: int = 20):
        """
        Subscribe to Hyperliquid orderbook updates

        Args:
            coin: Coin symbol (e.g., "BTC", "ETH")
            n_levels: Number of levels to subscribe to
        """
        if not self.hyperliquid_client:
            logger.warning("Hyperliquid client not initialized")
            return

        if coin in self.hyperliquid_subscriptions:
            logger.debug(f"Already subscribed to Hyperliquid {coin}")
            return

        try:

            async def callback(book: WsBook):
                await self._handle_hyperliquid_update(coin, book)

            await self.hyperliquid_client.subscribe_orderbook(
                coin=coin, callback=callback, n_levels=n_levels
            )
            self.hyperliquid_subscriptions.add(coin)
            logger.info(f"Subscribed to Hyperliquid {coin} orderbook")
        except Exception as e:
            logger.error(f"Failed to subscribe to Hyperliquid {coin}: {e}")
            self.hyperliquid_stats["errors"] += 1

    async def subscribe_lighter(self, market_index: int):
        """
        Subscribe to Lighter orderbook updates
        Fetches initial snapshot from REST API before streaming

        Args:
            market_index: Market index (0 for ETH, 1 for BTC, etc.)
        """
        if not self.lighter_client:
            logger.warning("Lighter client not initialized")
            return

        if market_index in self.lighter_subscriptions:
            logger.debug(f"Already subscribed to Lighter market {market_index}")
            return

        try:
            # Try to fetch initial deep snapshot from REST API (optional)
            if self.lighter_rest_client:
                try:
                    logger.info(
                        f"Fetching initial snapshot for Lighter market {market_index}"
                    )
                    initial_orderbook = (
                        await self.lighter_rest_client.get_orderbook_orders(
                            market_index
                        )
                    )

                    if initial_orderbook:
                        market = f"market_{market_index}"
                        await self.orderbook_manager.initialize_orderbook(
                            exchange="lighter",
                            market=market,
                            bids=initial_orderbook["bids"],
                            asks=initial_orderbook["asks"],
                            timestamp=datetime.now().timestamp(),
                        )

                        # Calculate depth info
                        bids = initial_orderbook["bids"]
                        asks = initial_orderbook["asks"]

                        # Calculate cumulative liquidity in USD
                        bid_liquidity_usd = sum(level.price * level.size for level in bids)
                        ask_liquidity_usd = sum(level.price * level.size for level in asks)

                        best_bid = bids[0].price if bids else None
                        worst_bid = bids[-1].price if bids else None
                        best_ask = asks[0].price if asks else None
                        worst_ask = asks[-1].price if asks else None

                        depth_info = ""
                        if best_bid and worst_bid and best_ask and worst_ask:
                            price_spread = best_ask - best_bid
                            depth_info = (
                                f", bid liquidity: ${bid_liquidity_usd:,.0f} "
                                f"(${worst_bid:.2f}-${best_bid:.2f}), "
                                f"ask liquidity: ${ask_liquidity_usd:,.0f} "
                                f"(${best_ask:.2f}-${worst_ask:.2f}), "
                                f"spread: ${price_spread:.2f}"
                            )

                        logger.success(
                            f"Initialized Lighter market {market_index} with "
                            f"{len(bids)} bids, {len(asks)} asks{depth_info} (REST API)"
                        )
                    else:
                        logger.warning(
                            f"REST API snapshot not available for market {market_index}, "
                            f"will rely on WebSocket data"
                        )
                except Exception as e:
                    logger.warning(
                        f"REST API snapshot failed for market {market_index}: {e}. "
                        f"Will rely on WebSocket data"
                    )

            # Now subscribe to real-time WebSocket updates
            async def callback(book: LighterOrderBook):
                await self._handle_lighter_update(market_index, book)

            await self.lighter_client.subscribe_orderbook(
                market_index=market_index, callback=callback
            )
            self.lighter_subscriptions.add(market_index)
            logger.info(
                f"Subscribed to Lighter market {market_index} WebSocket orderbook"
            )
        except Exception as e:
            logger.error(f"Failed to subscribe to Lighter market {market_index}: {e}")
            self.lighter_stats["errors"] += 1

    async def _handle_hyperliquid_update(self, coin: str, book: WsBook):
        """
        Handle Hyperliquid orderbook update

        Args:
            coin: Coin symbol
            book: WsBook orderbook data
        """
        try:
            # Convert to our internal format
            bids = [
                OrderBookLevel(price=float(level.px), size=float(level.sz))
                for level in book.bids
            ]
            asks = [
                OrderBookLevel(price=float(level.px), size=float(level.sz))
                for level in book.asks
            ]

            # Update orderbook manager (Hyperliquid sends full snapshots)
            await self.orderbook_manager.update_orderbook(
                exchange="hyperliquid",
                market=coin,
                bids=bids,
                asks=asks,
                timestamp=book.time / 1000,  # Convert ms to seconds
                is_snapshot=True,  # Hyperliquid sends full orderbook snapshots
            )

            self.hyperliquid_stats["messages_received"] += 1
            self.hyperliquid_stats["last_update"] = datetime.now().timestamp()

        except Exception as e:
            logger.error(f"Error handling Hyperliquid {coin} update: {e}")
            self.hyperliquid_stats["errors"] += 1

    async def _handle_lighter_update(self, market_index: int, book: LighterOrderBook):
        """
        Handle Lighter orderbook update (incremental)

        Args:
            market_index: Market index
            book: LighterOrderBook orderbook data
        """
        try:
            # Convert to our internal format
            bids = [
                OrderBookLevel(price=level.price, size=level.size)
                for level in book.bids
            ]
            asks = [
                OrderBookLevel(price=level.price, size=level.size)
                for level in book.asks
            ]

            # Use market index as market identifier
            market = f"market_{market_index}"

            # Apply incremental update to cache
            await self.orderbook_manager.update_orderbook(
                exchange="lighter",
                market=market,
                bids=bids,
                asks=asks,
                timestamp=(
                    book.offset / 1000 if book.offset else datetime.now().timestamp()
                ),
                is_snapshot=False,  # WebSocket sends incremental updates
            )

            self.lighter_stats["messages_received"] += 1
            self.lighter_stats["last_update"] = datetime.now().timestamp()

        except Exception as e:
            logger.error(f"Error handling Lighter market {market_index} update: {e}")
            self.lighter_stats["errors"] += 1

    async def unsubscribe_hyperliquid(self, coin: str):
        """
        Unsubscribe from Hyperliquid orderbook

        Args:
            coin: Coin symbol
        """
        # Note: The current HyperliquidWebSocket doesn't have unsubscribe
        # We just remove from our tracking
        if coin in self.hyperliquid_subscriptions:
            self.hyperliquid_subscriptions.remove(coin)
            logger.info(f"Unsubscribed from Hyperliquid {coin}")

    async def unsubscribe_lighter(self, market_index: int):
        """
        Unsubscribe from Lighter orderbook

        Args:
            market_index: Market index
        """
        # Note: The current LighterWebSocket doesn't have unsubscribe
        # We just remove from our tracking
        if market_index in self.lighter_subscriptions:
            self.lighter_subscriptions.remove(market_index)
            logger.info(f"Unsubscribed from Lighter market {market_index}")

    async def _periodic_rest_fetch(self):
        """
        Periodically fetch deep orderbook levels from Lighter REST API
        Runs every 5 seconds for subscribed markets
        """
        logger.info("Starting periodic REST fetch task (every 5 seconds)")

        while not self._should_stop:
            try:
                await asyncio.sleep(5)

                if not self.lighter_rest_client:
                    continue

                # Fetch orderbooks for all subscribed Lighter markets
                if self.lighter_subscriptions:
                    market_indices = list(self.lighter_subscriptions)

                    try:
                        orderbooks = (
                            await self.lighter_rest_client.get_multiple_orderbooks(
                                market_indices, depth=20
                            )
                        )

                        # Update orderbook manager with deep levels
                        if orderbooks:
                            for market_index, orderbook_data in orderbooks.items():
                                try:
                                    market = f"market_{market_index}"

                                    # Re-initialize with full REST snapshot
                                    await self.orderbook_manager.initialize_orderbook(
                                        exchange="lighter",
                                        market=market,
                                        bids=orderbook_data["bids"],
                                        asks=orderbook_data["asks"],
                                        timestamp=datetime.now().timestamp(),
                                    )

                                    # Calculate depth info
                                    bids = orderbook_data["bids"]
                                    asks = orderbook_data["asks"]

                                    # Calculate cumulative liquidity in USD
                                    bid_liquidity_usd = sum(level.price * level.size for level in bids)
                                    ask_liquidity_usd = sum(level.price * level.size for level in asks)

                                    best_bid = bids[0].price if bids else None
                                    best_ask = asks[0].price if asks else None

                                    depth_info = ""
                                    if best_bid and best_ask:
                                        depth_info = (
                                            f", bid liquidity: ${bid_liquidity_usd:,.0f}, "
                                            f"ask liquidity: ${ask_liquidity_usd:,.0f}"
                                        )

                                    logger.info(
                                        f"[REST] Lighter market {market_index}: "
                                        f"{len(bids)} bids, {len(asks)} asks{depth_info}"
                                    )

                                except Exception as e:
                                    logger.error(
                                        f"Error updating orderbook from REST for market {market_index}: {e}"
                                    )
                                    self.lighter_stats["errors"] += 1
                    except Exception as e:
                        logger.warning(
                            f"REST API fetch failed, skipping this cycle: {e}"
                        )

            except asyncio.CancelledError:
                logger.info("REST fetch task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic REST fetch: {e}")
                await asyncio.sleep(1)

    def get_hyperliquid_stats(self) -> ConnectionStats:
        """Get Hyperliquid connection statistics"""
        return ConnectionStats(
            exchange="hyperliquid",
            connected=self.hyperliquid_stats["connected"],
            last_update=self.hyperliquid_stats["last_update"],
            messages_received=self.hyperliquid_stats["messages_received"],
            errors=self.hyperliquid_stats["errors"],
        )

    def get_lighter_stats(self) -> ConnectionStats:
        """Get Lighter connection statistics"""
        return ConnectionStats(
            exchange="lighter",
            connected=self.lighter_stats["connected"],
            last_update=self.lighter_stats["last_update"],
            messages_received=self.lighter_stats["messages_received"],
            errors=self.lighter_stats["errors"],
        )

    async def stop(self):
        """Stop all exchange connections"""
        self._should_stop = True

        # Cancel REST fetch task
        if self._rest_fetch_task and not self._rest_fetch_task.done():
            self._rest_fetch_task.cancel()
            try:
                await self._rest_fetch_task
            except asyncio.CancelledError:
                pass

        tasks = []

        if self.hyperliquid_client:
            tasks.append(self.hyperliquid_client.disconnect())

        if self.lighter_client:
            tasks.append(self.lighter_client.disconnect())

        if self.lighter_rest_client:
            tasks.append(self.lighter_rest_client.close())

        await asyncio.gather(*tasks, return_exceptions=True)

        self.hyperliquid_stats["connected"] = False
        self.lighter_stats["connected"] = False

        logger.info("All exchange connections stopped")
