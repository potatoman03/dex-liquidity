"use client";

interface AssetSelectorProps {
  assets: string[];
  selectedAsset: string;
  onAssetChange: (asset: string) => void;
}

export default function AssetSelector({
  assets,
  selectedAsset,
  onAssetChange,
}: AssetSelectorProps) {
  return (
    <div className="flex items-center gap-3">
      <label htmlFor="asset-select" className="text-sm font-medium text-gray-400">
        Asset:
      </label>
      <select
        id="asset-select"
        value={selectedAsset}
        onChange={(e) => onAssetChange(e.target.value)}
        className="bg-gray-800 text-white border border-gray-700 rounded-lg px-4 py-2 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer hover:bg-gray-750 transition-colors"
      >
        {assets.map((asset) => (
          <option key={asset} value={asset} className="bg-gray-800">
            {asset}
          </option>
        ))}
      </select>
    </div>
  );
}
