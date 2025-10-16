"""
Hyperliquid WebSocket Client Implementation
"""

import asyncio
import json
from typing import Any, Dict, Optional, Set

from loguru import logger
from websockets.client import WebSocketClientProtocol, connect

from .types import (
    ErrorCallback,
    MessageCallback,
    OrderBookCallback,
    SubscriptionType,
    WsBook,
)


class HyperliquidWebSocket:
    """
    WebSocket client for Hyperliquid exchange

    Supports connecting to Hyperliquid's WebSocket API and subscribing to real-time data feeds,
    with a focus on orderbook streaming.

    Example:
        async with HyperliquidWebSocket() as client:
            await client.subscribe_orderbook("BTC", callback=lambda book: print(book))
            await asyncio.sleep(10)
    """

    # WebSocket URLs
    MAINNET_URL = "wss://api.hyperliquid.xyz/ws"
    TESTNET_URL = "wss://api.hyperliquid-testnet.xyz/ws"

    def __init__(
        self,
        testnet: bool = False,
        auto_reconnect: bool = True,
        reconnect_delay: float = 5.0,
    ):
        """
        Initialize Hyperliquid WebSocket client

        Args:
            testnet: If True, connect to testnet. Otherwise, connect to mainnet.
            auto_reconnect: If True, automatically reconnect on connection loss.
            reconnect_delay: Delay in seconds before attempting to reconnect.
        """
        self.url = self.TESTNET_URL if testnet else self.MAINNET_URL
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay

        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._orderbook_callbacks: Dict[str, OrderBookCallback] = {}
        self._message_callback: Optional[MessageCallback] = None
        self._error_callback: Optional[ErrorCallback] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._should_stop = False

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if the WebSocket is connected"""
        return self._connected and self._ws is not None

    async def connect(self) -> None:
        """
        Establish WebSocket connection to Hyperliquid

        Raises:
            ConnectionError: If connection fails
        """
        if self.is_connected:
            logger.warning("Already connected to WebSocket")
            return

        try:
            logger.info(f"Connecting to {self.url}")
            self._ws = await connect(self.url)
            self._connected = True
            self._should_stop = False
            logger.info("Successfully connected to Hyperliquid WebSocket")

            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_messages())

            # Resubscribe to all previous subscriptions
            await self._resubscribe()

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._connected = False
            raise ConnectionError(f"Failed to connect to WebSocket: {e}")

    async def disconnect(self) -> None:
        """
        Close the WebSocket connection gracefully
        """
        if not self.is_connected:
            logger.warning("Not connected to WebSocket")
            return

        try:
            self._should_stop = True
            self._connected = False

            # Cancel receive task
            if self._receive_task and not self._receive_task.done():
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass

            # Close WebSocket
            if self._ws:
                await self._ws.close()
                self._ws = None

            logger.info("Disconnected from Hyperliquid WebSocket")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def subscribe_orderbook(
        self,
        coin: str,
        callback: OrderBookCallback,
        n_levels: int = 20,
    ) -> None:
        """
        Subscribe to orderbook updates for a specific coin

        Args:
            coin: Trading pair symbol (e.g., "BTC", "ETH")
            callback: Callback function to handle orderbook updates
            n_levels: Number of price levels to receive (max 100, default 20)

        Raises:
            ValueError: If n_levels is invalid
            ConnectionError: If not connected
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to WebSocket. Call connect() first.")

        if n_levels < 1 or n_levels > 100:
            raise ValueError("n_levels must be between 1 and 100")

        subscription_key = f"l2Book:{coin}"

        # Store callback
        self._orderbook_callbacks[subscription_key] = callback

        # Build subscription message
        subscription = {
            "method": "subscribe",
            "subscription": {
                "type": SubscriptionType.L2_BOOK.value,
                "coin": coin,
                "nLevels": n_levels,
            },
        }

        # Store subscription for reconnection
        self._subscriptions[subscription_key] = subscription

        # Send subscription
        await self._send_message(subscription)
        logger.info(f"Subscribed to orderbook for {coin} with {n_levels} levels")

    async def unsubscribe_orderbook(self, coin: str) -> None:
        """
        Unsubscribe from orderbook updates for a specific coin

        Args:
            coin: Trading pair symbol (e.g., "BTC", "ETH")
        """
        if not self.is_connected:
            logger.warning("Not connected to WebSocket")
            return

        subscription_key = f"l2Book:{coin}"

        if subscription_key not in self._subscriptions:
            logger.warning(f"Not subscribed to orderbook for {coin}")
            return

        # Build unsubscribe message
        unsubscribe = {
            "method": "unsubscribe",
            "subscription": self._subscriptions[subscription_key]["subscription"],
        }

        # Send unsubscribe
        await self._send_message(unsubscribe)

        # Remove from storage
        del self._subscriptions[subscription_key]
        del self._orderbook_callbacks[subscription_key]

        logger.info(f"Unsubscribed from orderbook for {coin}")

    def set_message_callback(self, callback: MessageCallback) -> None:
        """
        Set a callback for all incoming messages

        Args:
            callback: Callback function to handle all messages
        """
        self._message_callback = callback

    def set_error_callback(self, callback: ErrorCallback) -> None:
        """
        Set a callback for error handling

        Args:
            callback: Callback function to handle errors
        """
        self._error_callback = callback

    async def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a message through the WebSocket"""
        if not self._ws:
            raise ConnectionError("WebSocket not connected")

        try:
            await self._ws.send(json.dumps(message))
            # logger.debug(f"Sent message: {message}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            if self._error_callback:
                self._error_callback(e)
            raise

    async def _receive_messages(self) -> None:
        """
        Continuously receive and process messages from WebSocket
        """
        while not self._should_stop and self.is_connected:
            try:
                if not self._ws:
                    break

                message = await self._ws.recv()
                await self._handle_message(message)

            except asyncio.CancelledError:
                logger.info("Receive task cancelled")
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")

                if self._error_callback:
                    self._error_callback(e)

                # Attempt reconnection if enabled
                if self.auto_reconnect and not self._should_stop:
                    logger.info(
                        f"Attempting to reconnect in {self.reconnect_delay} seconds..."
                    )
                    await asyncio.sleep(self.reconnect_delay)
                    try:
                        self._connected = False
                        await self.connect()
                    except Exception as reconnect_error:
                        logger.error(f"Reconnection failed: {reconnect_error}")
                else:
                    break

    async def _handle_message(self, message: str) -> None:
        """
        Parse and handle incoming WebSocket message

        Args:
            message: Raw message string from WebSocket
        """
        try:
            data = json.loads(message)

            # Call generic message callback if set
            if self._message_callback:
                self._message_callback(data)

            # Handle specific message types
            channel = data.get("channel")

            if channel == "l2Book":
                await self._handle_orderbook_update(data)
            else:
                pass
                # logger.debug(f"Received message on channel: {channel}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            if self._error_callback:
                self._error_callback(e)

    async def _handle_orderbook_update(self, data: Dict[str, Any]) -> None:
        """
        Handle orderbook update messages

        Args:
            data: Parsed message data
        """
        try:
            book_data = data.get("data")
            if not book_data:
                logger.warning("Received l2Book message with no data")
                return

            # logger.debug(f"Received orderbook data: {book_data}")

            # Parse orderbook
            ws_book = WsBook.from_dict(book_data)

            # Find and call appropriate callback
            subscription_key = f"l2Book:{ws_book.coin}"
            callback = self._orderbook_callbacks.get(subscription_key)

            if callback:
                await callback(ws_book)
            else:
                logger.warning(f"No callback registered for {subscription_key}")

        except Exception as e:
            logger.error(f"Error handling orderbook update: {e}", exc_info=True)
            logger.error(f"Data that caused error: {data}")
            if self._error_callback:
                self._error_callback(e)

    async def _resubscribe(self) -> None:
        """Resubscribe to all active subscriptions after reconnection"""
        if not self._subscriptions:
            return

        logger.info(f"Resubscribing to {len(self._subscriptions)} subscriptions")

        for subscription in self._subscriptions.values():
            try:
                await self._send_message(subscription)
            except Exception as e:
                logger.error(f"Failed to resubscribe: {e}")
