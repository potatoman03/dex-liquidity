"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";

interface DualPriceChartProps {
  lighterPrice: number | null;
  hyperliquidPrice: number | null;
  asset?: string;
}

export default function DualPriceChart({
  lighterPrice,
  hyperliquidPrice,
  asset = "ETH",
}: DualPriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lighterSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const hyperliquidSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [updateCount, setUpdateCount] = useState(0);

  const lighterDataRef = useRef<Array<{ time: number; value: number }>>([]);
  const hyperliquidDataRef = useRef<Array<{ time: number; value: number }>>([]);
  const lighterLastTimestampRef = useRef<number>(0);
  const hyperliquidLastTimestampRef = useRef<number>(0);
  const lighterLastPriceRef = useRef<number | null>(null);
  const hyperliquidLastPriceRef = useRef<number | null>(null);

  // Clear chart data when asset changes
  useEffect(() => {
    if (lighterSeriesRef.current && hyperliquidSeriesRef.current) {
      // Clear the series data
      lighterSeriesRef.current.setData([]);
      hyperliquidSeriesRef.current.setData([]);

      // Clear the refs
      lighterDataRef.current = [];
      hyperliquidDataRef.current = [];
      lighterLastTimestampRef.current = 0;
      hyperliquidLastTimestampRef.current = 0;
      lighterLastPriceRef.current = null;
      hyperliquidLastPriceRef.current = null;
    }
  }, [asset]);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#1f1f1f" },
        horzLines: { color: "#1f1f1f" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 300,
      rightPriceScale: {
        borderColor: "#2e2e2e",
      },
      timeScale: {
        borderColor: "#2e2e2e",
        timeVisible: true,
        secondsVisible: true,
        rightOffset: 5,
        barSpacing: 3,
        fixLeftEdge: true,
        fixRightEdge: false,
      },
      crosshair: {
        mode: 1,
      },
    });

    // Add Lighter series (green)
    const lighterSeries = chart.addLineSeries({
      color: "#22c55e",
      lineWidth: 2,
      title: "Lighter",
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });

    // Add Hyperliquid series (blue)
    const hyperliquidSeries = chart.addLineSeries({
      color: "#3b82f6",
      lineWidth: 2,
      title: "Hyperliquid",
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });

    chartRef.current = chart;
    lighterSeriesRef.current = lighterSeries;
    hyperliquidSeriesRef.current = hyperliquidSeries;

    // Fit content initially
    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  // Update Lighter price
  useEffect(() => {
    if (lighterPrice !== null && lighterSeriesRef.current && chartRef.current) {
      const timestamp = Math.floor(Date.now() / 1000);

      // Skip if price hasn't changed and we're still in the same second
      if (timestamp === lighterLastTimestampRef.current && lighterPrice === lighterLastPriceRef.current) {
        return;
      }

      if (timestamp === lighterLastTimestampRef.current) {
        // Update existing point
        const newPoint = { time: timestamp, value: lighterPrice };
        lighterSeriesRef.current.update(newPoint);
        if (lighterDataRef.current.length > 0) {
          lighterDataRef.current[lighterDataRef.current.length - 1] = newPoint;
        }
      } else if (timestamp > lighterLastTimestampRef.current) {
        // New second, add new point
        const newPoint = { time: timestamp, value: lighterPrice };
        lighterDataRef.current.push(newPoint);
        lighterSeriesRef.current.update(newPoint);

        // Remove data points older than 60 seconds
        const cutoff = timestamp - 60;
        lighterDataRef.current = lighterDataRef.current.filter((p) => p.time >= cutoff);
      } else {
        return;
      }

      lighterLastTimestampRef.current = timestamp;
      lighterLastPriceRef.current = lighterPrice;
      setUpdateCount((prev) => prev + 1);

      updateVisibleRange();
    }
  }, [lighterPrice]);

  // Update Hyperliquid price
  useEffect(() => {
    if (hyperliquidPrice !== null && hyperliquidSeriesRef.current && chartRef.current) {
      const timestamp = Math.floor(Date.now() / 1000);

      // Skip if price hasn't changed and we're still in the same second
      if (timestamp === hyperliquidLastTimestampRef.current && hyperliquidPrice === hyperliquidLastPriceRef.current) {
        return;
      }

      if (timestamp === hyperliquidLastTimestampRef.current) {
        // Update existing point
        const newPoint = { time: timestamp, value: hyperliquidPrice };
        hyperliquidSeriesRef.current.update(newPoint);
        if (hyperliquidDataRef.current.length > 0) {
          hyperliquidDataRef.current[hyperliquidDataRef.current.length - 1] = newPoint;
        }
      } else if (timestamp > hyperliquidLastTimestampRef.current) {
        // New second, add new point
        const newPoint = { time: timestamp, value: hyperliquidPrice };
        hyperliquidDataRef.current.push(newPoint);
        hyperliquidSeriesRef.current.update(newPoint);

        // Remove data points older than 60 seconds
        const cutoff = timestamp - 60;
        hyperliquidDataRef.current = hyperliquidDataRef.current.filter((p) => p.time >= cutoff);
      } else {
        return;
      }

      hyperliquidLastTimestampRef.current = timestamp;
      hyperliquidLastPriceRef.current = hyperliquidPrice;
      setUpdateCount((prev) => prev + 1);

      updateVisibleRange();
    }
  }, [hyperliquidPrice]);

  const updateVisibleRange = () => {
    if (!chartRef.current) return;

    const allData = [...lighterDataRef.current, ...hyperliquidDataRef.current];
    if (allData.length > 0) {
      const timestamp = Math.floor(Date.now() / 1000);
      const oldestTime = Math.min(...allData.map((p) => p.time));
      chartRef.current.timeScale().setVisibleRange({
        from: Math.max(oldestTime, timestamp - 60),
        to: timestamp + 5,
      });
    }
  };

  return (
    <div className="flex flex-col">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold">Live Mid Prices - {asset}</h3>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-green-500"></div>
            <span className="text-sm text-gray-400">Lighter:</span>
            <span className="text-lg font-mono text-green-500">
              {lighterPrice ? `$${lighterPrice.toFixed(2)}` : "N/A"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-blue-500"></div>
            <span className="text-sm text-gray-400">Hyperliquid:</span>
            <span className="text-lg font-mono text-blue-500">
              {hyperliquidPrice ? `$${hyperliquidPrice.toFixed(2)}` : "N/A"}
            </span>
          </div>
        </div>
      </div>
      <div className="bg-gray-900 rounded-lg p-4">
        <div ref={chartContainerRef} className="w-full" />
      </div>
    </div>
  );
}
