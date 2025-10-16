"""
Liquidity calculator for orderbook depth analysis
"""

from typing import Dict, List

from loguru import logger

from .config import LIQUIDITY_SIZES
from .models import LiquidityMetric, LiquidityMetrics, OrderBookLevel, OrderBookSnapshot


class LiquidityCalculator:
    """
    Calculate execution costs and liquidity metrics for orderbooks
    """

    @staticmethod
    def calculate_buy_cost(
        asks: List[OrderBookLevel],
        size_usd: float,
        current_price: float,
        orderbook: OrderBookSnapshot,
    ) -> LiquidityMetric:
        """
        Calculate cost to execute a buy order (walk up the asks)

        Args:
            asks: List of ask levels (sorted ascending by price)
            size_usd: Size to execute in USD
            current_price: Current mid price for reference

        Returns:
            LiquidityMetric with execution details
        """
        if not asks:
            return LiquidityMetric(
                size_usd=size_usd,
                total_cost=0,
                avg_price=0,
                slippage_bps=0,
                levels_used=0,
                feasible=False,
            )

        remaining_usd = size_usd
        total_cost = 0
        total_tokens = 0
        levels_used = 0

        for level in asks:
            if remaining_usd <= 0:
                break

            level_liquidity_usd = level.price * level.size

            if level_liquidity_usd >= remaining_usd:
                # This level has enough liquidity
                tokens_to_buy = remaining_usd / level.price
                total_cost += remaining_usd
                total_tokens += tokens_to_buy
                levels_used += 1
                remaining_usd = 0
                break
            else:
                # Consume entire level
                total_cost += level_liquidity_usd
                total_tokens += level.size
                remaining_usd -= level_liquidity_usd
                levels_used += 1

        # Check if order is feasible
        feasible = remaining_usd <= 0.01  # Allow small rounding errors

        # Calculate metrics
        if total_tokens > 0:
            avg_price = total_cost / total_tokens
            slippage = avg_price - current_price if current_price > 0 else 0
            slippage_bps = (slippage / current_price * 10000) if current_price > 0 else 0
        else:
            avg_price = 0
            slippage_bps = 0

        # If not feasible, mark with very high slippage to indicate problem
        if not feasible and total_tokens > 0:
            # Use the calculated slippage, don't artificially inflate it
            # The natural slippage from partial fill already shows the issue
            pass

        return LiquidityMetric(
            size_usd=size_usd,
            total_cost=total_cost,
            avg_price=avg_price,
            slippage_bps=slippage_bps,
            levels_used=levels_used,
            feasible=feasible,
        )

    @staticmethod
    def calculate_sell_cost(
        bids: List[OrderBookLevel],
        size_usd: float,
        current_price: float,
        orderbook: OrderBookSnapshot,
    ) -> LiquidityMetric:
        """
        Calculate proceeds from executing a sell order (walk down the bids)

        Args:
            bids: List of bid levels (sorted descending by price)
            size_usd: Size to execute in USD
            current_price: Current mid price for reference

        Returns:
            LiquidityMetric with execution details
        """
        if not bids:
            return LiquidityMetric(
                size_usd=size_usd,
                total_cost=0,
                avg_price=0,
                slippage_bps=0,
                levels_used=0,
                feasible=False,
            )

        remaining_usd = size_usd
        total_proceeds = 0
        total_tokens = 0
        levels_used = 0

        for level in bids:
            if remaining_usd <= 0:
                break

            level_liquidity_usd = level.price * level.size

            if level_liquidity_usd >= remaining_usd:
                # This level has enough liquidity
                tokens_to_sell = remaining_usd / level.price
                total_proceeds += remaining_usd
                total_tokens += tokens_to_sell
                levels_used += 1
                remaining_usd = 0
                break
            else:
                # Consume entire level
                total_proceeds += level_liquidity_usd
                total_tokens += level.size
                remaining_usd -= level_liquidity_usd
                levels_used += 1

        # Check if order is feasible
        feasible = remaining_usd <= 0.01

        # Calculate metrics
        if total_tokens > 0:
            avg_price = total_proceeds / total_tokens
            slippage = current_price - avg_price if current_price > 0 else 0
            slippage_bps = (slippage / current_price * 10000) if current_price > 0 else 0
        else:
            avg_price = 0
            slippage_bps = 0

        # If not feasible, mark with very high slippage to indicate problem
        if not feasible and total_tokens > 0:
            # Use the calculated slippage, don't artificially inflate it
            # The natural slippage from partial fill already shows the issue
            pass

        return LiquidityMetric(
            size_usd=size_usd,
            total_cost=total_proceeds,  # For sells, "cost" is actually proceeds
            avg_price=avg_price,
            slippage_bps=slippage_bps,
            levels_used=levels_used,
            feasible=feasible,
        )

    @staticmethod
    def calculate_all_metrics(
        orderbook: OrderBookSnapshot, sizes: List[float] = None
    ) -> LiquidityMetrics:
        """
        Calculate liquidity metrics for all standard sizes

        Args:
            orderbook: OrderBook snapshot
            sizes: Custom size levels (defaults to LIQUIDITY_SIZES)

        Returns:
            LiquidityMetrics with all size levels
        """
        if sizes is None:
            sizes = LIQUIDITY_SIZES

        if orderbook.mid_price is None:
            logger.warning(
                f"No mid price available for {orderbook.exchange} {orderbook.market}"
            )
            return LiquidityMetrics(
                exchange=orderbook.exchange,
                market=orderbook.market,
                timestamp=orderbook.timestamp,
                metrics={},
            )

        metrics = {}
        current_price = orderbook.mid_price

        for size in sizes:
            # Calculate buy-side metrics (market buy order)
            buy_metric = LiquidityCalculator.calculate_buy_cost(
                orderbook.asks, size, current_price, orderbook
            )

            # Calculate sell-side metrics (market sell order)
            sell_metric = LiquidityCalculator.calculate_sell_cost(
                orderbook.bids, size, current_price, orderbook
            )

            # Store both buy and sell metrics
            metrics[str(int(size))] = {
                "buy": buy_metric,
                "sell": sell_metric,
            }

        return LiquidityMetrics(
            exchange=orderbook.exchange,
            market=orderbook.market,
            timestamp=orderbook.timestamp,
            metrics=metrics,
        )

    @staticmethod
    def format_for_frontend(metrics: LiquidityMetrics) -> Dict[str, Dict[str, float]]:
        """
        Format liquidity metrics for frontend consumption

        Returns simplified dict with buy and sell metrics:
        {"1000": {"buy_cost": 1000.50, "buy_avg_price": 3500.0, "buy_slippage_bps": 5.0,
                  "sell_proceeds": 999.50, "sell_avg_price": 3495.0, "sell_slippage_bps": 5.0}, ...}
        """
        formatted = {}

        for size_str, metric_pair in metrics.metrics.items():
            if isinstance(metric_pair, dict):
                # New format with buy/sell separation
                buy_metric = metric_pair["buy"]
                sell_metric = metric_pair["sell"]

                formatted[size_str] = {
                    "buy_cost": round(buy_metric.total_cost, 2),
                    "buy_avg_price": round(buy_metric.avg_price, 2),
                    "buy_slippage_bps": round(buy_metric.slippage_bps, 2),
                    "sell_proceeds": round(sell_metric.total_cost, 2),
                    "sell_avg_price": round(sell_metric.avg_price, 2),
                    "sell_slippage_bps": round(sell_metric.slippage_bps, 2),
                }
            else:
                # Legacy format (single metric) - treat as buy-side only
                formatted[size_str] = {
                    "buy_cost": round(metric_pair.total_cost, 2),
                    "buy_avg_price": round(metric_pair.avg_price, 2),
                    "buy_slippage_bps": round(metric_pair.slippage_bps, 2),
                    "sell_proceeds": 0,
                    "sell_avg_price": 0,
                    "sell_slippage_bps": 0,
                }

        return formatted
