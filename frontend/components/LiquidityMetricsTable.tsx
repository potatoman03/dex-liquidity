"use client";

import { LiquidityMetrics } from "@/hooks/useWebSocket";

interface LiquidityMetricsTableProps {
  exchange: string;
  market: string;
  metrics: LiquidityMetrics | null;
}

export default function LiquidityMetricsTable({
  exchange,
  market,
  metrics,
}: LiquidityMetricsTableProps) {
  if (!metrics || metrics.metrics.length === 0) {
    return (
      <div className="flex items-center justify-center p-8 text-gray-400">
        No liquidity metrics available
      </div>
    );
  }

  const formatUSD = (usd: number) =>
    `$${usd.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}`;

  const formatPrice = (price: number) => price?.toFixed(2) ?? "0.00";

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">
        {exchange.toUpperCase()} - {market} Liquidity
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-2 text-gray-400">Size (USD)</th>
              <th className="text-right py-2 text-gray-400">Buy Cost</th>
              <th className="text-right py-2 text-gray-400">Buy Avg Price</th>
              <th className="text-right py-2 text-gray-400">Buy Slippage (bps)</th>
              <th className="text-right py-2 text-gray-400">Sell Proceeds</th>
              <th className="text-right py-2 text-gray-400">Sell Avg Price</th>
              <th className="text-right py-2 text-gray-400">Sell Slippage (bps)</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {metrics.metrics.map((metric, idx) => (
              <tr
                key={idx}
                className="border-b border-gray-800 hover:bg-gray-800/30"
              >
                <td className="py-2">{formatUSD(metric.size_usd)}</td>
                <td className="text-right text-red-500">
                  {formatUSD(metric.buy_cost)}
                </td>
                <td className="text-right">${formatPrice(metric.buy_avg_price)}</td>
                <td className="text-right">
                  {metric.buy_slippage_bps ? Math.abs(metric.buy_slippage_bps).toFixed(2) : "N/A"}
                </td>
                <td className="text-right text-green-500">
                  {formatUSD(metric.sell_proceeds)}
                </td>
                <td className="text-right">
                  ${formatPrice(metric.sell_avg_price)}
                </td>
                <td className="text-right">
                  {metric.sell_slippage_bps ? Math.abs(metric.sell_slippage_bps).toFixed(2) : "N/A"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
