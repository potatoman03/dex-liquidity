"""
Lighter REST API client for fetching deep orderbook levels
"""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger

from .models import OrderBookLevel


class LighterRestClient:
    """
    REST API client for Lighter exchange
    Fetches deep orderbook levels as a backup to WebSocket data
    """

    MAINNET_URL = "https://mainnet.zklighter.elliot.ai"
    TESTNET_URL = "https://testnet.zklighter.elliot.ai"

    def __init__(self, testnet: bool = False):
        """
        Initialize Lighter REST client

        Args:
            testnet: If True, use testnet. Otherwise, use mainnet.
        """
        self.base_url = self.TESTNET_URL if testnet else self.MAINNET_URL
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Create aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info(f"Lighter REST client initialized: {self.base_url}")

    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Lighter REST client closed")

    async def get_orderbook_orders(
        self, market_index: int, depth: Optional[int] = None
    ) -> Optional[Dict[str, List[OrderBookLevel]]]:
        """
        Fetch deep orderbook levels for a market

        Args:
            market_index: Market index (0 for ETH, 1 for BTC, etc.)
            depth: Optional depth limit (number of levels to fetch)

        Returns:
            Dict with 'bids' and 'asks' lists of OrderBookLevel, or None on error
        """
        if not self.session:
            logger.error("Session not initialized. Call connect() first.")
            return None

        url = f"{self.base_url}/api/v1/orderBookOrders"

        # Build request payload
        payload = {"market_id": market_index, "limit": 100}

        if depth is not None:
            payload["depth"] = depth

        try:
            logger.debug(f"GET {url} with params: {payload}")

            async with self.session.get(url, params=payload) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to fetch orderbook for market {market_index}: "
                        f"HTTP {response.status} - {await response.text()}"
                    )
                    return None

                try:
                    data = await response.json()
                except Exception as e:
                    # Try to get text for debugging
                    try:
                        response_text = await response.text()
                        logger.error(
                            f"Failed to parse JSON response: {e}. Response: {response_text[:500]}"
                        )
                    except:
                        logger.error(f"Failed to parse JSON response: {e}")
                    return None

                # Parse response
                # Format: {"bids": [...], "asks": [...]}
                # Each level: {"price": "...", "remaining_base_amount": "...", ...}
                bids = []
                asks = []

                for bid_data in data.get("bids", []):
                    try:
                        bids.append(
                            OrderBookLevel(
                                price=float(bid_data["price"]),
                                size=float(bid_data["remaining_base_amount"]),
                            )
                        )
                    except (KeyError, ValueError) as e:
                        logger.warning(
                            f"Failed to parse bid level: {e} - data: {bid_data}"
                        )
                        continue

                for ask_data in data.get("asks", []):
                    try:
                        asks.append(
                            OrderBookLevel(
                                price=float(ask_data["price"]),
                                size=float(ask_data["remaining_base_amount"]),
                            )
                        )
                    except (KeyError, ValueError) as e:
                        logger.warning(
                            f"Failed to parse ask level: {e} - data: {ask_data}"
                        )
                        continue

                logger.debug(
                    f"Fetched {len(bids)} bids and {len(asks)} asks for market {market_index}"
                )

                return {"bids": bids, "asks": asks}

        except aiohttp.ClientError as e:
            logger.error(
                f"Network error fetching orderbook for market {market_index}: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error fetching orderbook for market {market_index}: {e}",
                exc_info=True,
            )
            return None

    async def get_multiple_orderbooks(
        self, market_indices: List[int], depth: Optional[int] = 20
    ) -> Dict[int, Dict[str, List[OrderBookLevel]]]:
        """
        Fetch orderbooks for multiple markets concurrently

        Args:
            market_indices: List of market indices to fetch
            depth: Optional depth limit

        Returns:
            Dict mapping market_index to orderbook data
        """
        tasks = [
            self.get_orderbook_orders(market_index, depth)
            for market_index in market_indices
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        orderbooks = {}
        for market_index, result in zip(market_indices, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching market {market_index}: {result}")
            elif result is not None:
                orderbooks[market_index] = result

        return orderbooks
