"use client";

import { LiquidityMetrics } from "@/hooks/useWebSocket";
import { useState, useEffect } from "react";

interface ExecutionLeaderboardProps {
  lighterMetrics: LiquidityMetrics | null;
  hyperliquidMetrics: LiquidityMetrics | null;
}

interface SizeSnapshot {
  size_usd: number;
  buyWinner: "lighter" | "hyperliquid" | "tie";
  sellWinner: "lighter" | "hyperliquid" | "tie";
}

interface HistoricalSnapshot {
  timestamp: number;
  sizes: SizeSnapshot[];
}

interface SizeStats {
  size_usd: number;
  lighterBuyWins: number;
  hyperliquidBuyWins: number;
  lighterSellWins: number;
  hyperliquidSellWins: number;
  totalSnapshots: number;
}

export default function ExecutionLeaderboard({
  lighterMetrics,
  hyperliquidMetrics,
}: ExecutionLeaderboardProps) {
  const [history, setHistory] = useState<HistoricalSnapshot[]>([]);
  const [snapshotCount, setSnapshotCount] = useState(0);

  // Capture snapshot every 10 seconds
  useEffect(() => {
    const captureSnapshot = () => {
      if (!lighterMetrics || !hyperliquidMetrics) {
        return;
      }

      const sizes: SizeSnapshot[] = [];

      for (const metric of lighterMetrics.metrics) {
        const hyperliquidMetric = hyperliquidMetrics.metrics.find(
          (m) => m.size_usd === metric.size_usd
        );

        if (!hyperliquidMetric) continue;

        // Determine buy winner
        const lighterBuySlippage = metric.buy_slippage_bps;
        const hyperliquidBuySlippage = hyperliquidMetric.buy_slippage_bps;
        const buyWinner =
          lighterBuySlippage < hyperliquidBuySlippage
            ? "lighter"
            : lighterBuySlippage > hyperliquidBuySlippage
            ? "hyperliquid"
            : "tie";

        // Determine sell winner
        const lighterSellSlippage = metric.sell_slippage_bps;
        const hyperliquidSellSlippage = hyperliquidMetric.sell_slippage_bps;
        const sellWinner =
          lighterSellSlippage < hyperliquidSellSlippage
            ? "lighter"
            : lighterSellSlippage > hyperliquidSellSlippage
            ? "hyperliquid"
            : "tie";

        sizes.push({
          size_usd: metric.size_usd,
          buyWinner,
          sellWinner,
        });
      }

      const snapshot: HistoricalSnapshot = {
        timestamp: Date.now(),
        sizes,
      };

      setHistory((prev) => {
        // Keep last 60 snapshots (10 minutes of history)
        const updated = [...prev, snapshot];
        return updated.slice(-60);
      });

      setSnapshotCount((prev) => prev + 1);
    };

    // Capture initial snapshot
    captureSnapshot();

    // Then capture every 10 seconds
    const interval = setInterval(captureSnapshot, 10000);

    return () => clearInterval(interval);
  }, [lighterMetrics, hyperliquidMetrics]);

  // Calculate aggregate stats from history
  const sizeStats: SizeStats[] = [];

  if (history.length > 0) {
    // Get unique sizes from first snapshot
    const sizes = history[0].sizes.map((s) => s.size_usd);

    for (const size of sizes) {
      let lighterBuyWins = 0;
      let hyperliquidBuyWins = 0;
      let lighterSellWins = 0;
      let hyperliquidSellWins = 0;

      for (const snapshot of history) {
        const sizeData = snapshot.sizes.find((s) => s.size_usd === size);
        if (!sizeData) continue;

        if (sizeData.buyWinner === "lighter") lighterBuyWins++;
        else if (sizeData.buyWinner === "hyperliquid") hyperliquidBuyWins++;

        if (sizeData.sellWinner === "lighter") lighterSellWins++;
        else if (sizeData.sellWinner === "hyperliquid") hyperliquidSellWins++;
      }

      sizeStats.push({
        size_usd: size,
        lighterBuyWins,
        hyperliquidBuyWins,
        lighterSellWins,
        hyperliquidSellWins,
        totalSnapshots: history.length,
      });
    }
  }

  if (sizeStats.length === 0) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
        <h2 className="text-xl font-semibold mb-4">
          Historical Execution Leaderboard
        </h2>
        <div className="text-gray-400 text-center py-8">
          Collecting data... Next update in 10 seconds
        </div>
      </div>
    );
  }

  const formatSize = (size: number) => {
    if (size >= 1000000) return `$${(size / 1000000).toFixed(1)}M`;
    if (size >= 1000) return `$${(size / 1000).toFixed(0)}K`;
    return `$${size}`;
  };

  return (
    <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">
          Historical Execution Leaderboard
        </h2>
        <span className="text-xs text-gray-500">
          {snapshotCount} snapshots collected (updates every 10s)
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-2 px-3 text-gray-400 font-semibold">
                Size
              </th>
              <th className="text-center py-2 px-3 text-gray-400 font-semibold">
                Best Buy
              </th>
              <th className="text-center py-2 px-3 text-gray-400 font-semibold">
                Buy Win Rate
              </th>
              <th className="text-center py-2 px-3 text-gray-400 font-semibold">
                Best Sell
              </th>
              <th className="text-center py-2 px-3 text-gray-400 font-semibold">
                Sell Win Rate
              </th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {sizeStats.map((stat, idx) => {
              const buyWinRate =
                (stat.lighterBuyWins /
                  (stat.lighterBuyWins + stat.hyperliquidBuyWins)) *
                100;
              const sellWinRate =
                (stat.lighterSellWins /
                  (stat.lighterSellWins + stat.hyperliquidSellWins)) *
                100;

              const bestBuyExchange = stat.lighterBuyWins > stat.hyperliquidBuyWins ? "Lighter" :
                                     stat.lighterBuyWins < stat.hyperliquidBuyWins ? "Hyperliquid" : "Tie";
              const bestSellExchange = stat.lighterSellWins > stat.hyperliquidSellWins ? "Lighter" :
                                      stat.lighterSellWins < stat.hyperliquidSellWins ? "Hyperliquid" : "Tie";

              return (
                <tr
                  key={idx}
                  className="border-b border-gray-800 hover:bg-gray-800/30"
                >
                  <td className="py-3 px-3 font-semibold">
                    {formatSize(stat.size_usd)}
                  </td>
                  <td className="py-3 px-3 text-center">
                    <span
                      className={
                        bestBuyExchange === "Lighter"
                          ? "text-green-500 font-semibold"
                          : bestBuyExchange === "Hyperliquid"
                          ? "text-blue-500 font-semibold"
                          : "text-gray-400"
                      }
                    >
                      {bestBuyExchange}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex flex-1 rounded-full h-2 min-w-[100px] overflow-hidden">
                      <div
                        className="bg-green-500 h-2 transition-all"
                        style={{ width: `${buyWinRate}%` }}
                      />
                      <div
                        className="bg-blue-500 h-2 transition-all"
                        style={{ width: `${100 - buyWinRate}%` }}
                      />
                    </div>
                  </td>
                  <td className="py-3 px-3 text-center">
                    <span
                      className={
                        bestSellExchange === "Lighter"
                          ? "text-green-500 font-semibold"
                          : bestSellExchange === "Hyperliquid"
                          ? "text-blue-500 font-semibold"
                          : "text-gray-400"
                      }
                    >
                      {bestSellExchange}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex flex-1 rounded-full h-2 min-w-[100px] overflow-hidden">
                      <div
                        className="bg-green-500 h-2 transition-all"
                        style={{ width: `${sellWinRate}%` }}
                      />
                      <div
                        className="bg-blue-500 h-2 transition-all"
                        style={{ width: `${100 - sellWinRate}%` }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
