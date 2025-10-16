"use client";

import { LiquidityMetrics } from "@/hooks/useWebSocket";
import { useMemo, useEffect } from "react";

interface LiquiditySummaryProps {
  lighterMetrics: LiquidityMetrics | null;
  hyperliquidMetrics: LiquidityMetrics | null;
}

interface Recommendation {
  size: string;
  buyExchange: string;
  buyCost: number;
  buySavings: number;
  buySlippageBps: number;
  sellExchange: string;
  sellProceeds: number;
  sellSavings: number;
  sellSlippageBps: number;
}

export default function LiquiditySummary({
  lighterMetrics,
  hyperliquidMetrics,
}: LiquiditySummaryProps) {
  // ALL HOOKS MUST BE AT THE TOP - before any conditional returns

  // Debug logging
  useEffect(() => {
    if (lighterMetrics && hyperliquidMetrics) {
      console.log("[LiquiditySummary] Metrics updated:", {
        lighter: {
          timestamp: lighterMetrics.timestamp,
          count: lighterMetrics.metrics.length,
        },
        hyperliquid: {
          timestamp: hyperliquidMetrics.timestamp,
          count: hyperliquidMetrics.metrics.length,
        },
      });
    }
  }, [lighterMetrics, hyperliquidMetrics]);

  const lastUpdateTime = useMemo(() => {
    const lighterTime = lighterMetrics?.timestamp || 0;
    const hyperliquidTime = hyperliquidMetrics?.timestamp || 0;
    return Math.max(lighterTime, hyperliquidTime);
  }, [lighterMetrics, hyperliquidMetrics]);

  const recommendations = useMemo(() => {
    if (!lighterMetrics || !hyperliquidMetrics) {
      return null;
    }

    console.log("[LiquiditySummary] Recalculating recommendations");
    const recs: Recommendation[] = [];

    // Compare each size level
    for (const metric of lighterMetrics.metrics) {
      const sizeStr = metric.size_usd.toString();
      const hyperliquidMetric = hyperliquidMetrics.metrics.find(
        (m) => m.size_usd === metric.size_usd
      );

      if (!hyperliquidMetric) continue;

      // Compare buy slippage (lower slippage = better execution)
      const lighterBuySlippage = metric.buy_slippage_bps;
      const hyperliquidBuySlippage = hyperliquidMetric.buy_slippage_bps;
      const buyExchange = lighterBuySlippage <= hyperliquidBuySlippage ? "Lighter" : "Hyperliquid";
      const buySlippageBps = buyExchange === "Lighter" ? lighterBuySlippage : hyperliquidBuySlippage;
      const buyCost = buyExchange === "Lighter" ? metric.buy_cost : hyperliquidMetric.buy_cost;
      const buySavings = Math.abs(metric.buy_cost - hyperliquidMetric.buy_cost);

      // Debug first size level
      if (metric.size_usd === 1000) {
        console.log(`[LiquiditySummary] $1K Buy comparison:`, {
          lighterSlippage: lighterBuySlippage,
          hyperliquidSlippage: hyperliquidBuySlippage,
          selected: buyExchange,
          slippageDiff: Math.abs(lighterBuySlippage - hyperliquidBuySlippage),
        });
      }

      // Compare sell slippage (lower slippage = better execution)
      const lighterSellSlippage = metric.sell_slippage_bps;
      const hyperliquidSellSlippage = hyperliquidMetric.sell_slippage_bps;
      const sellExchange = lighterSellSlippage <= hyperliquidSellSlippage ? "Lighter" : "Hyperliquid";
      const sellSlippageBps = sellExchange === "Lighter" ? lighterSellSlippage : hyperliquidSellSlippage;
      const sellProceeds = sellExchange === "Lighter" ? metric.sell_proceeds : hyperliquidMetric.sell_proceeds;
      const sellSavings = Math.abs(metric.sell_proceeds - hyperliquidMetric.sell_proceeds);

      recs.push({
        size: sizeStr,
        buyExchange,
        buyCost,
        buySavings,
        buySlippageBps,
        sellExchange,
        sellProceeds,
        sellSavings,
        sellSlippageBps,
      });
    }

    console.log("[LiquiditySummary] Generated recommendations:", recs.length);
    return recs;
  }, [lighterMetrics?.timestamp, hyperliquidMetrics?.timestamp, lighterMetrics?.metrics, hyperliquidMetrics?.metrics]);

  // Formatting functions (not hooks, can be anywhere)
  const formatUSD = (usd: number) =>
    `$${usd.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}`;

  const formatSize = (size: string) => {
    const num = parseInt(size);
    if (num >= 1000000) return `$${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `$${(num / 1000).toFixed(0)}K`;
    return `$${num}`;
  };

  // Conditional return AFTER all hooks
  if (!recommendations) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
        <h2 className="text-xl font-semibold mb-4">Best Execution Summary</h2>
        <div className="text-gray-400 text-center py-8">
          Waiting for liquidity data from both exchanges...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Best Execution Summary</h2>
        {lastUpdateTime > 0 && (
          <span className="text-xs text-gray-500">
            Last update: {new Date(lastUpdateTime * 1000).toLocaleTimeString()}
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-2 px-3 text-gray-400 font-semibold">Size</th>
              <th className="text-left py-2 px-3 text-gray-400 font-semibold">Best Buy</th>
              <th className="text-right py-2 px-3 text-gray-400 font-semibold">Buy Cost</th>
              <th className="text-right py-2 px-3 text-gray-400 font-semibold">Cost (bps)</th>
              <th className="text-left py-2 px-3 text-gray-400 font-semibold">Best Sell</th>
              <th className="text-right py-2 px-3 text-gray-400 font-semibold">Sell Proceeds</th>
              <th className="text-right py-2 px-3 text-gray-400 font-semibold">Cost (bps)</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {recommendations.map((rec, idx) => (
              <tr
                key={idx}
                className="border-b border-gray-800 hover:bg-gray-800/30"
              >
                <td className="py-2 px-3 font-semibold">{formatSize(rec.size)}</td>
                <td className="py-2 px-3">
                  <span
                    className={
                      rec.buyExchange === "Lighter"
                        ? "text-green-500 font-semibold"
                        : "text-blue-500 font-semibold"
                    }
                  >
                    {rec.buyExchange}
                  </span>
                </td>
                <td className="text-right py-2 px-3 text-red-400">
                  {formatUSD(rec.buyCost)}
                </td>
                <td className="text-right py-2 px-3 text-orange-400">
                  {Math.abs(rec.buySlippageBps).toFixed(2)}
                </td>
                <td className="py-2 px-3">
                  <span
                    className={
                      rec.sellExchange === "Lighter"
                        ? "text-green-500 font-semibold"
                        : "text-blue-500 font-semibold"
                    }
                  >
                    {rec.sellExchange}
                  </span>
                </td>
                <td className="text-right py-2 px-3 text-green-400">
                  {formatUSD(rec.sellProceeds)}
                </td>
                <td className="text-right py-2 px-3 text-orange-400">
                  {Math.abs(rec.sellSlippageBps).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
