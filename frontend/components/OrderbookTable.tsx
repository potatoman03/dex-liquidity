"use client";

import { OrderBookData } from "@/hooks/useWebSocket";

interface OrderbookTableProps {
  orderbook: OrderBookData | null;
}

export default function OrderbookTable({
  orderbook,
}: OrderbookTableProps) {
  if (!orderbook) {
    return (
      <div className="flex items-center justify-center p-8 text-gray-400">
        Waiting for orderbook data...
      </div>
    );
  }

  const formatPrice = (price: number) => price?.toFixed(2) ?? "0.00";
  const formatSize = (size: number) => size?.toFixed(4) ?? "0.0000";
  const formatUSD = (usd: number | undefined) => {
    if (usd === undefined || usd === null || isNaN(usd)) return "$0";
    return `$${usd.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  const maxCumulativeUSD = Math.max(
    orderbook.bids[0]?.cumulative_usd || 0,
    orderbook.asks[0]?.cumulative_usd || 0,
    1 // Minimum value to avoid division by zero
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="border-b border-gray-700 pb-4">
        <h2 className="text-2xl font-bold mb-2">
          {orderbook.exchange.toUpperCase()} - {orderbook.market}
        </h2>
        <div className="flex gap-6 text-sm">
          <div>
            <span className="text-gray-400">Mid Price: </span>
            <span className="font-mono text-lg">
              {orderbook.mid ? `$${formatPrice(orderbook.mid)}` : "N/A"}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Spread: </span>
            <span className="font-mono">
              {orderbook.spread ? `$${formatPrice(orderbook.spread)}` : "N/A"}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Spread (bps): </span>
            <span className="font-mono">
              {orderbook.spread_bps !== null ? orderbook.spread_bps.toFixed(2) : "N/A"}
            </span>
          </div>
        </div>
      </div>

      {/* Orderbook */}
      <div className="flex flex-col gap-6">
        {/* Asks (Sell Orders) */}
        <div>
          <div className="mb-2">
            <h3 className="text-lg font-semibold text-red-500">Asks (Sell)</h3>
          </div>
          <div className="space-y-1">
            {/* Header */}
            <div className="grid grid-cols-4 gap-2 text-xs text-gray-400 font-semibold pb-2 border-b border-gray-700">
              <div className="text-right">Price</div>
              <div className="text-right">Size</div>
              <div className="text-right">Cumulative</div>
              <div className="text-right">Total USD</div>
            </div>
            {/* Ask levels (highest price at top, inverted) */}
            {[...orderbook.asks].reverse().slice(0, 20).map((level, idx) => {
              const depthPercent = level.cumulative_usd
                ? Math.min((level.cumulative_usd / maxCumulativeUSD) * 100, 100)
                : 0;
              return (
                <div
                  key={idx}
                  className="relative grid grid-cols-4 gap-2 text-xs font-mono py-1 hover:bg-gray-800/50"
                >
                  {/* Depth bar */}
                  <div
                    className="absolute inset-0 bg-red-600/30"
                    style={{ width: `${depthPercent}%` }}
                  />
                  <div className="relative text-right text-red-500">
                    {formatPrice(level.price)}
                  </div>
                  <div className="relative text-right">{formatSize(level.size)}</div>
                  <div className="relative text-right">
                    {formatSize(level.cumulative_size)}
                  </div>
                  <div className="relative text-right text-gray-400">
                    {formatUSD(level.cumulative_usd)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Bids (Buy Orders) */}
        <div>
          <div className="mb-2">
            <h3 className="text-lg font-semibold text-green-500">Bids (Buy)</h3>
          </div>
          <div className="space-y-1">
            {/* Header */}
            <div className="grid grid-cols-4 gap-2 text-xs text-gray-400 font-semibold pb-2 border-b border-gray-700">
              <div className="text-right">Price</div>
              <div className="text-right">Size</div>
              <div className="text-right">Cumulative</div>
              <div className="text-right">Total USD</div>
            </div>
            {/* Bid levels */}
            {orderbook.bids.slice(0, 20).map((level, idx) => {
              const depthPercent = level.cumulative_usd
                ? Math.min((level.cumulative_usd / maxCumulativeUSD) * 100, 100)
                : 0;
              return (
                <div
                  key={idx}
                  className="relative grid grid-cols-4 gap-2 text-xs font-mono py-1 hover:bg-gray-800/50"
                >
                  {/* Depth bar */}
                  <div
                    className="absolute inset-0 bg-green-600/30"
                    style={{ width: `${depthPercent}%` }}
                  />
                  <div className="relative text-right text-green-500">
                    {formatPrice(level.price)}
                  </div>
                  <div className="relative text-right">{formatSize(level.size)}</div>
                  <div className="relative text-right">
                    {formatSize(level.cumulative_size)}
                  </div>
                  <div className="relative text-right text-gray-400">
                    {formatUSD(level.cumulative_usd)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
