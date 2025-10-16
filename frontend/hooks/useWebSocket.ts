import { useEffect, useRef, useState } from "react";

export interface OrderBookLevel {
  price: number;
  size: number;
  cumulative_size: number;
  cumulative_usd: number;
}

export interface OrderBookData {
  exchange: string;
  market: string;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  mid: number | null;
  spread: number | null;
  spread_bps: number | null;
  timestamp: number;
}

export interface LiquidityMetric {
  size_usd: number;
  buy_cost: number;
  buy_avg_price: number;
  buy_slippage_bps: number;
  sell_proceeds: number;
  sell_avg_price: number;
  sell_slippage_bps: number;
}

export interface LiquidityMetrics {
  exchange: string;
  market: string;
  metrics: LiquidityMetric[];
  timestamp: number;
}

export interface PriceUpdate {
  exchange: string;
  market: string;
  mid: number;
  timestamp: number;
}

type MessageType = "orderbook_update" | "liquidity_metrics" | "price_update";

interface OrderbookUpdateMessage extends OrderBookData {
  type: "orderbook_update";
}

interface LiquidityMetricsMessage {
  type: "liquidity_metrics";
  exchange: string;
  market: string;
  metrics: Record<string, {
    buy_cost: number;
    buy_avg_price: number;
    buy_slippage_bps: number;
    sell_proceeds: number;
    sell_avg_price: number;
    sell_slippage_bps: number;
  }>;
  timestamp: number;
}

interface PriceUpdateMessage extends PriceUpdate {
  type: "price_update";
}

type WebSocketMessage = OrderbookUpdateMessage | LiquidityMetricsMessage | PriceUpdateMessage;

interface UseWebSocketReturn {
  orderbooks: Record<string, OrderBookData>;
  liquidityMetrics: Record<string, LiquidityMetrics>;
  prices: Record<string, PriceUpdate>;
  connected: boolean;
  subscribe: (markets: string[]) => void;
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [orderbooks, setOrderbooks] = useState<Record<string, OrderBookData>>({});
  const [liquidityMetrics, setLiquidityMetrics] = useState<Record<string, LiquidityMetrics>>({});
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({});
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const subscribedMarketsRef = useRef<Set<string>>(new Set());

  const connect = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
      setConnected(true);

      // Resubscribe to previously subscribed markets
      if (subscribedMarketsRef.current.size > 0) {
        const markets = Array.from(subscribedMarketsRef.current);
        console.log("Resubscribing to markets:", markets);
        ws.send(
          JSON.stringify({
            action: "subscribe",
            markets,
          })
        );
      }

      // Start ping interval to keep connection alive
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000); // Ping every 30 seconds
    };

    ws.onmessage = (event) => {
      try {
        const message: any = JSON.parse(event.data);

        // Handle ping/pong
        if (message.type === "ping") {
          ws.send(JSON.stringify({ type: "pong" }));
          return;
        }
        if (message.type === "pong") {
          // Connection is alive
          return;
        }

        switch (message.type) {
          case "orderbook_update": {
            const key = `${message.exchange}_${message.market}`;

            // Calculate cumulative fields if not provided
            const bids = message.bids.map((level, idx, arr) => {
              const cumSize = arr.slice(0, idx + 1).reduce((sum, l) => sum + l.size, 0);
              const cumUsd = arr.slice(0, idx + 1).reduce((sum, l) => sum + l.price * l.size, 0);
              return {
                ...level,
                cumulative_size: level.cumulative_size ?? cumSize,
                cumulative_usd: level.cumulative_usd ?? cumUsd,
              };
            });

            const asks = message.asks.map((level, idx, arr) => {
              const cumSize = arr.slice(0, idx + 1).reduce((sum, l) => sum + l.size, 0);
              const cumUsd = arr.slice(0, idx + 1).reduce((sum, l) => sum + l.price * l.size, 0);
              return {
                ...level,
                cumulative_size: level.cumulative_size ?? cumSize,
                cumulative_usd: level.cumulative_usd ?? cumUsd,
              };
            });

            setOrderbooks((prev) => ({
              ...prev,
              [key]: {
                exchange: message.exchange,
                market: message.market,
                bids,
                asks,
                mid: message.mid,
                spread: message.spread,
                spread_bps: message.spread_bps,
                timestamp: message.timestamp,
              },
            }));
            break;
          }
          case "liquidity_metrics": {
            const key = `${message.exchange}_${message.market}`;
            // Convert metrics from Dict[str, Dict[str, float]] to array format
            const metricsArray = Object.entries(message.metrics).map(([size, data]) => ({
              size_usd: parseFloat(size),
              buy_cost: data.buy_cost,
              buy_avg_price: data.buy_avg_price,
              buy_slippage_bps: data.buy_slippage_bps,
              sell_proceeds: data.sell_proceeds,
              sell_avg_price: data.sell_avg_price,
              sell_slippage_bps: data.sell_slippage_bps,
            }));

            setLiquidityMetrics((prev) => ({
              ...prev,
              [key]: {
                exchange: message.exchange,
                market: message.market,
                metrics: metricsArray,
                timestamp: message.timestamp,
              },
            }));
            break;
          }
          case "price_update": {
            const key = `${message.exchange}_${message.market}`;
            setPrices((prev) => ({
              ...prev,
              [key]: {
                exchange: message.exchange,
                market: message.market,
                mid: message.price,
                timestamp: message.timestamp,
              },
            }));
            break;
          }
        }
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      // Error will trigger onclose which handles reconnection
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setConnected(false);

      // Clear ping interval
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }

      // Attempt to reconnect with exponential backoff
      const reconnect = () => {
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log("Attempting to reconnect...");
          connect();
        }, 3000);
      };

      reconnect();
    };
  };

  const subscribe = (markets: string[]) => {
    // Store markets for resubscription on reconnect
    markets.forEach((market) => subscribedMarketsRef.current.add(market));

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: "subscribe",
          markets,
        })
      );
    }
  };

  useEffect(() => {
    connect();

    return () => {
      // Cleanup on unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url]);

  return {
    orderbooks,
    liquidityMetrics,
    prices,
    connected,
    subscribe,
  };
}
