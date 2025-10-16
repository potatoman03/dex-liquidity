import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DEX Liquidity Viewer",
  description: "Real-time orderbook aggregation across multiple DEXs",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
