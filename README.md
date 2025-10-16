# DEX Liquidity Aggregator

Real-time orderbook aggregation and liquidity comparison for Hyperliquid and Lighter DEX exchanges.

## Prerequisites

- Python 3.10+
- Node.js 18+

## Setup

### Backend

1. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the backend server:
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at http://localhost:8000

### Frontend

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Run the development server:
```bash
npm run dev
```

Frontend runs at http://localhost:3000
