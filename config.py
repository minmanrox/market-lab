SYMBOL = "QQQ"

# Network
FEED_HOST = "127.0.0.1"   # ← set to Zybo's IP when connecting hardware
FEED_PORT = 5000           # UDP (market data out to Zybo)
OMS_HOST  = "0.0.0.0"     # listen on all interfaces so Zybo can connect
OMS_PORT  = 5001           # TCP (orders in from Zybo, fills out)
UI_PORT   = 5002           # HTTP / WebSocket dashboard

# Feed cadence
FEED_INTERVAL_MS = 100     # one price update every 100 ms (10 Hz)

# Synthetic GBM price generation
SYNTHETIC_START_PRICE = 470.00   # approx QQQ
SYNTHETIC_VOLATILITY  = 0.0003   # sigma per tick  (~30% annualised)
SYNTHETIC_SPREAD_BPS  = 2        # full bid/ask spread in basis points

# OMS simulation
FILL_LATENCY_MS_MIN = 5
FILL_LATENCY_MS_MAX = 50
REJECTION_RATE      = 0.02       # 2 % of orders randomly rejected
SLIPPAGE_BPS        = 1          # market-order slippage (each side)
