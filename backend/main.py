"""
FastAPI backend server for DEX orderbook aggregation
"""

import asyncio
from datetime import datetime
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .connection_manager import ConnectionManager
from .liquidity_calculator import LiquidityCalculator
from .models import (
    LiquidityMetricsUpdate,
    OrderBookUpdate,
    PriceUpdate,
    SubscriptionMessage,
)
from .orderbook_manager import OrderBookManager
from .config import LIGHTER_MARKET_MAP, LIGHTER_MARKET_REVERSE_STR, BROADCAST_FREQUENCY_HZ, AVAILABLE_ASSETS

# Initialize FastAPI app
app = FastAPI(
    title="DEX Orderbook Aggregator",
    description="Real-time orderbook aggregation for Hyperliquid and Lighter",
    version="1.0.0",
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
orderbook_manager: OrderBookManager = None
connection_manager: ConnectionManager = None

# Track connected WebSocket clients and their subscriptions
connected_clients: Set[WebSocket] = set()
client_subscriptions: Dict[WebSocket, Set[str]] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global orderbook_manager, connection_manager

    logger.info("Starting DEX Orderbook Aggregator backend...")

    # Initialize managers
    orderbook_manager = OrderBookManager(price_history_seconds=3600)
    connection_manager = ConnectionManager(orderbook_manager)

    # Register callback for immediate tick-level price updates
    orderbook_manager.set_price_update_callback(broadcast_price_update_immediately)

    # Start exchange connections
    await connection_manager.start()

    # Start background task for broadcasting updates
    asyncio.create_task(broadcast_updates())

    logger.success("Backend started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global connection_manager

    logger.info("Shutting down DEX Orderbook Aggregator backend...")

    if connection_manager:
        await connection_manager.stop()

    logger.success("Backend shutdown complete")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "DEX Orderbook Aggregator",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    orderbook_stats = orderbook_manager.get_stats()
    hyperliquid_stats = connection_manager.get_hyperliquid_stats()
    lighter_stats = connection_manager.get_lighter_stats()

    return {
        "orderbook_manager": orderbook_stats,
        "exchanges": {
            "hyperliquid": hyperliquid_stats.dict(),
            "lighter": lighter_stats.dict(),
        },
        "connected_clients": len(connected_clients),
    }


@app.get("/markets")
async def get_markets():
    """Get all tracked markets"""
    markets = await orderbook_manager.get_all_markets()
    return {
        "markets": [{"exchange": ex, "market": mkt} for ex, mkt in markets],
        "count": len(markets),
    }


@app.get("/assets")
async def get_assets():
    """Get all available trading assets"""
    return {
        "assets": AVAILABLE_ASSETS,
        "count": len(AVAILABLE_ASSETS),
    }


async def heartbeat_monitor(websocket: WebSocket):
    """
    Monitor WebSocket connection health with periodic pings
    Sends ping every 30 seconds to keep connection alive
    """
    try:
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception as e:
                logger.debug(f"Failed to send heartbeat ping: {e}")
                break
    except asyncio.CancelledError:
        pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time orderbook updates

    Protocol:
    - Client sends: {"action": "subscribe", "markets": ["BTC", "ETH", ...]}
    - Client sends: {"action": "ping"} for heartbeat
    - Server sends: OrderBookUpdate, LiquidityMetricsUpdate, PriceUpdate messages
    - Server sends: {"type": "pong"} in response to ping
    """
    await websocket.accept()
    connected_clients.add(websocket)
    client_subscriptions[websocket] = set()

    logger.info(f"Client connected. Total clients: {len(connected_clients)}")

    # Start heartbeat task
    heartbeat_task = asyncio.create_task(heartbeat_monitor(websocket))

    try:
        while True:
            # Receive messages from client with timeout
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
            except asyncio.TimeoutError:
                # No message received in 60 seconds, check if connection is alive
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    logger.warning("Client connection dead (timeout)")
                    break
                continue

            message_type = data.get("action") or data.get("type")

            if message_type == "subscribe":
                message = SubscriptionMessage(**data)
                await handle_subscribe(websocket, message.markets)
            elif message_type == "unsubscribe":
                message = SubscriptionMessage(**data)
                await handle_unsubscribe(websocket, message.markets)
            elif message_type == "ping":
                # Respond to client ping
                await websocket.send_json({"type": "pong"})
            elif message_type == "pong":
                # Client responded to our ping, connection is alive
                pass

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cancel heartbeat task
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        # Clean up
        connected_clients.discard(websocket)
        if websocket in client_subscriptions:
            del client_subscriptions[websocket]
        logger.info(f"Client removed. Total clients: {len(connected_clients)}")


async def handle_subscribe(websocket: WebSocket, markets: list[str]):
    """
    Handle client subscription request

    Args:
        websocket: Client websocket
        markets: List of market symbols (e.g., ["BTC", "ETH"])
    """
    for market in markets:
        # Add to client subscriptions
        client_subscriptions[websocket].add(market)

        # Subscribe to Hyperliquid
        await connection_manager.subscribe_hyperliquid(market)

        # Subscribe to Lighter if market is mapped
        if market in LIGHTER_MARKET_MAP:
            market_index = LIGHTER_MARKET_MAP[market]
            await connection_manager.subscribe_lighter(market_index)

        logger.info(
            f"Client subscribed to {market}. "
            f"Client has {len(client_subscriptions[websocket])} subscriptions"
        )

        # Send initial orderbook snapshot if available (Hyperliquid)
        orderbook = await orderbook_manager.get_orderbook("hyperliquid", market)
        if orderbook:
            await send_orderbook_update(websocket, orderbook)

        # Send initial liquidity metrics if available (Hyperliquid)
        metrics = await orderbook_manager.get_liquidity_metrics("hyperliquid", market)
        if metrics:
            await send_liquidity_metrics(websocket, metrics)


async def handle_unsubscribe(websocket: WebSocket, markets: list[str]):
    """
    Handle client unsubscription request

    Args:
        websocket: Client websocket
        markets: List of market symbols to unsubscribe from
    """
    for market in markets:
        client_subscriptions[websocket].discard(market)
        logger.info(
            f"Client unsubscribed from {market}. "
            f"Client has {len(client_subscriptions[websocket])} subscriptions"
        )


async def broadcast_updates():
    """
    Background task to broadcast orderbook updates to subscribed clients
    """
    logger.info("Starting broadcast task...")
    sleep_time = 1.0 / BROADCAST_FREQUENCY_HZ

    while True:
        try:
            await asyncio.sleep(sleep_time)

            if not connected_clients:
                continue

            # Get all current orderbooks
            orderbooks = await orderbook_manager.get_all_orderbooks()

            for orderbook in orderbooks:
                # Broadcast to clients subscribed to this market
                await broadcast_orderbook_update(orderbook)

        except Exception as e:
            logger.error(f"Error in broadcast task: {e}")
            await asyncio.sleep(1)


async def broadcast_orderbook_update(orderbook):
    """Broadcast orderbook update to subscribed clients"""
    # Get the subscription key (coin symbol)
    if orderbook.exchange == "lighter":
        subscription_key = LIGHTER_MARKET_REVERSE_STR.get(orderbook.market, orderbook.market)
    else:
        subscription_key = orderbook.market

    disconnected = set()

    for client in connected_clients:
        if subscription_key in client_subscriptions.get(client, set()):
            try:
                await send_orderbook_update(client, orderbook)

                # Also send liquidity metrics
                metrics = await orderbook_manager.get_liquidity_metrics(
                    orderbook.exchange, orderbook.market
                )
                if metrics:
                    await send_liquidity_metrics(client, metrics)

                # Note: Price updates are now sent immediately via callback, not here

            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.add(client)

    # Remove disconnected clients
    for client in disconnected:
        connected_clients.discard(client)
        if client in client_subscriptions:
            del client_subscriptions[client]


async def broadcast_price_update_immediately(
    exchange: str, market: str, price: float, timestamp: float
):
    """
    Broadcast tick-level price update immediately to subscribed clients
    Called by orderbook_manager whenever mid price changes
    """
    # Get the subscription key (coin symbol)
    if exchange == "lighter":
        subscription_key = LIGHTER_MARKET_REVERSE_STR.get(market, market)
    else:
        subscription_key = market

    disconnected = set()

    for client in connected_clients:
        if subscription_key in client_subscriptions.get(client, set()):
            try:
                await send_price_update(client, exchange, market, price, timestamp)
            except Exception as e:
                logger.debug(f"Error sending price update to client: {e}")
                disconnected.add(client)

    # Remove disconnected clients
    for client in disconnected:
        connected_clients.discard(client)
        if client in client_subscriptions:
            del client_subscriptions[client]


async def send_orderbook_update(websocket: WebSocket, orderbook):
    """Send orderbook update to a client"""
    update = OrderBookUpdate(
        exchange=orderbook.exchange,
        market=orderbook.market,
        bids=[
            {"price": level.price, "size": level.size} for level in orderbook.bids[:20]
        ],  # Top 20 levels
        asks=[
            {"price": level.price, "size": level.size} for level in orderbook.asks[:20]
        ],
        mid=orderbook.mid_price,
        spread=orderbook.spread,
        spread_bps=orderbook.spread_bps,
        timestamp=orderbook.timestamp,
    )
    await websocket.send_json(update.dict())


async def send_liquidity_metrics(websocket: WebSocket, metrics):
    """Send liquidity metrics to a client"""
    formatted = LiquidityCalculator.format_for_frontend(metrics)
    update = LiquidityMetricsUpdate(
        exchange=metrics.exchange,
        market=metrics.market,
        metrics=formatted,
        timestamp=metrics.timestamp,
    )
    await websocket.send_json(update.dict())


async def send_price_update(
    websocket: WebSocket, exchange: str, market: str, price: float, timestamp: float
):
    """Send price update to a client"""
    update = PriceUpdate(
        exchange=exchange, market=market, price=price, timestamp=timestamp
    )
    await websocket.send_json(update.dict())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
