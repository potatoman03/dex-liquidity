"use client";

import { useEffect, useState } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import OrderbookTable from "@/components/OrderbookTable";
import DualPriceChart from "@/components/DualPriceChart";
import LiquiditySummary from "@/components/LiquiditySummary";
import LiquidityMetricsTable from "@/components/LiquidityMetricsTable";
import ExecutionLeaderboard from "@/components/ExecutionLeaderboard";
import AssetSelector from "@/components/AssetSelector";

// Asset to Lighter market mapping
const LIGHTER_MARKET_MAP: Record<string, string> = {
  ETH: "market_0",
  BTC: "market_1",
  SOL: "market_2",
};

const AVAILABLE_ASSETS = ["ETH", "BTC", "SOL"];

export default function Home() {
  const [selectedAsset, setSelectedAsset] = useState("ETH");

  const { orderbooks, liquidityMetrics, connected, subscribe } = useWebSocket(
    "ws://localhost:8000/ws"
  );

  useEffect(() => {
    if (connected) {
      // Subscribe to selected asset on both exchanges
      subscribe([selectedAsset]);
    }
  }, [connected, selectedAsset]);

  const lighterMarket = LIGHTER_MARKET_MAP[selectedAsset];
  const lighterOrderbook = orderbooks[`lighter_${lighterMarket}`] || null;
  const lighterMetrics = liquidityMetrics[`lighter_${lighterMarket}`] || null;

  const hyperliquidOrderbook = orderbooks[`hyperliquid_${selectedAsset}`] || null;
  const hyperliquidMetrics = liquidityMetrics[`hyperliquid_${selectedAsset}`] || null;

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        {/* Connection Status and Asset Selector */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                connected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-sm text-gray-400">
              {connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <AssetSelector
            assets={AVAILABLE_ASSETS}
            selectedAsset={selectedAsset}
            onAssetChange={setSelectedAsset}
          />
        </div>

        {/* Title */}
        <h1 className="text-4xl font-bold mb-8">
          DEX Liquidity Viewer - {selectedAsset}
        </h1>

        {/* Dual Price Chart */}
        <div className="mb-8">
          <DualPriceChart
            lighterPrice={lighterOrderbook?.mid ?? null}
            hyperliquidPrice={hyperliquidOrderbook?.mid ?? null}
            asset={selectedAsset}
          />
        </div>

        {/* Execution Leaderboard */}
        <div className="mb-8">
          <ExecutionLeaderboard
            lighterMetrics={lighterMetrics}
            hyperliquidMetrics={hyperliquidMetrics}
          />
        </div>

        {/* Best Execution Summary */}
        <div className="mb-8">
          <LiquiditySummary
            lighterMetrics={lighterMetrics}
            hyperliquidMetrics={hyperliquidMetrics}
          />
        </div>

        {/* Liquidity Metrics - Side by Side */}
        <div className="grid grid-cols-2 gap-8 mb-8">
          {/* Lighter Liquidity Metrics */}
          <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
            <LiquidityMetricsTable
              exchange="lighter"
              market={lighterMarket}
              metrics={lighterMetrics}
            />
          </div>

          {/* Hyperliquid Liquidity Metrics */}
          <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
            <LiquidityMetricsTable
              exchange="hyperliquid"
              market={selectedAsset}
              metrics={hyperliquidMetrics}
            />
          </div>
        </div>

        {/* Orderbooks - Side by Side */}
        <div className="grid grid-cols-2 gap-8">
          {/* Lighter Orderbook */}
          <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
            <OrderbookTable orderbook={lighterOrderbook} />
          </div>

          {/* Hyperliquid Orderbook */}
          <div className="bg-gray-900 rounded-lg p-6 shadow-xl">
            <OrderbookTable orderbook={hyperliquidOrderbook} />
          </div>
        </div>
      </div>
    </main>
  );
}
