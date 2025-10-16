"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, LineData } from "lightweight-charts";

interface PriceChartProps {
  exchange: string;
  market: string;
  currentPrice: number | null;
}

export default function PriceChart({
  exchange,
  market,
  currentPrice,
}: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [updateCount, setUpdateCount] = useState(0);
  const dataPointsRef = useRef<Array<{ time: number; value: number }>>([]);
  const lastTimestampRef = useRef<number>(0);
  const lastPriceRef = useRef<number | null>(null);

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

    const lineSeries = chart.addLineSeries({
      color: "#22c55e",
      lineWidth: 2,
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });

    chartRef.current = chart;
    seriesRef.current = lineSeries;

    // Fit content initially (will be overridden when data arrives)
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

  // Update chart with new price data
  useEffect(() => {
    if (currentPrice !== null && seriesRef.current && chartRef.current) {
      const timestamp = Math.floor(Date.now() / 1000);

      // Skip if price hasn't changed and we're still in the same second
      if (timestamp === lastTimestampRef.current && currentPrice === lastPriceRef.current) {
        return;
      }

      // If we're in the same second but price changed, use the same timestamp
      // (lightweight-charts will update the last point)
      if (timestamp === lastTimestampRef.current) {
        // Update the existing point with new price
        const newPoint = { time: timestamp, value: currentPrice };
        seriesRef.current.update(newPoint);

        // Update the last point in dataPoints
        if (dataPointsRef.current.length > 0) {
          dataPointsRef.current[dataPointsRef.current.length - 1] = newPoint;
        }
      } else if (timestamp > lastTimestampRef.current) {
        // New second, add new point
        const newPoint = { time: timestamp, value: currentPrice };
        dataPointsRef.current.push(newPoint);
        seriesRef.current.update(newPoint);

        // Remove data points older than 60 seconds
        const cutoff = timestamp - 60;
        dataPointsRef.current = dataPointsRef.current.filter((p) => p.time >= cutoff);
      } else {
        // Timestamp is older than last, skip (out of order)
        return;
      }

      lastTimestampRef.current = timestamp;
      lastPriceRef.current = currentPrice;
      setUpdateCount((prev) => prev + 1);

      // Maintain 60-second rolling window (only if we have data)
      if (dataPointsRef.current.length > 0) {
        const oldestTime = Math.min(...dataPointsRef.current.map(p => p.time));
        chartRef.current.timeScale().setVisibleRange({
          from: Math.max(oldestTime, timestamp - 60),
          to: timestamp + 5, // Add a bit of padding on the right
        });
      }
    }
  }, [currentPrice]);

  return (
    <div className="flex flex-col">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          Live Mid Price - {exchange.toUpperCase()} {market}
        </h3>
        <div className="text-xl font-mono text-green-500">
          {currentPrice ? `$${currentPrice.toFixed(2)}` : "N/A"}
        </div>
      </div>
      <div className="bg-gray-900 rounded-lg p-4">
        <div ref={chartContainerRef} className="w-full" />
      </div>
    </div>
  );
}
