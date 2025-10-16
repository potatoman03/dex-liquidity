"""
Configuration for DEX orderbook aggregator
"""

# Lighter market index mappings
# Maps coin symbols to Lighter market indices
LIGHTER_MARKET_MAP = {
    "ETH": 0,
    "BTC": 1,
    "SOL": 2,
}

# Reverse mapping: Lighter market index to coin symbol
LIGHTER_MARKET_REVERSE = {
    0: "ETH",
    1: "BTC",
    2: "SOL",
}

# Alternative: using strings for consistency with orderbook manager storage
LIGHTER_MARKET_REVERSE_STR = {
    "market_0": "ETH",
    "market_1": "BTC",
    "market_2": "SOL",
}

# Available assets for trading (used by frontend)
AVAILABLE_ASSETS = ["ETH", "BTC", "SOL"]

# Standard liquidity sizes to calculate (in USD)
LIQUIDITY_SIZES = [1_000, 5_000, 10_000, 50_000, 100_000, 200_000, 500_000, 1_000_000]

# Broadcast frequency (Hz) for orderbook snapshots and liquidity metrics
BROADCAST_FREQUENCY_HZ = 10

# Send price updates immediately (tick-level) when orderbook changes
IMMEDIATE_PRICE_UPDATES = True

# Price history retention (seconds)
PRICE_HISTORY_SECONDS = 3600  # 1 hour
