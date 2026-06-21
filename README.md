# market-lab

Simulated automated trading system. Generates realistic market data, processes buy/sell orders, and drives a live web dashboard. Designed to interface with a Zybo FPGA over Ethernet so the PL can run automated trade logic.

```
                    ┌─────────────────────────────────┐
                    │          market-lab (PC)        │
                    │                                 │
  ┌──────────┐  UDP │  ┌──────────┐    ┌───────────┐  │
  │  Zybo PL │◄─────┼──│   Feed   │    │    UI     │  │
  │ (trade   │      │  │  Server  │    │ dashboard │  │
  │  logic)  │  TCP │  └────┬─────┘    └───────────┘  │
  │          │◄────►┼───────┤                         │
  └──────────┘      │  ┌────▼──────┐                  │
                    │  │ Processor │                  │
                    │  │   (OMS)   │                  │
                    │  └───────────┘                  │
                    └─────────────────────────────────┘
```

## Components

| Component | File | Description |
|---|---|---|
| Feed | `feed/server.py` | Generates/replays prices, broadcasts binary QUOTE frames over UDP |
| Processor | `processor/server.py` | TCP order server, matching engine, fills resting limit orders |
| UI | `ui/app.py` | Flask + WebSocket dashboard with live chart and order entry |
| Protocol | `common/protocol.py` | Binary frame encode/decode (shared by all components) |
| Zybo header | `zybo/protocol.h` | Drop-in C header for PS-side integration |

## Quick start

```bash
pip install -r requirements.txt
python3 run.py
# open http://localhost:5002
```

**CSV replay** (Yahoo Finance OHLCV format):
```bash
python3 run.py --csv QQQ.csv
```

Download historical data from Yahoo Finance → History → Download.

## Dashboard

- **Price bar** — live bid, ask, mid, spread updated at 10 Hz
- **Chart** — bid/ask lines with fill markers (TradingView Lightweight Charts)
- **Order entry** — market or limit orders; keyboard shortcuts `B` / `S` / `Enter`
- **Portfolio** — position, avg cost, unrealized/realized/total P&L
- **Fills blotter** — execution history, last 50 fills
- **Resting orders** — open limit orders with cancel buttons

## Connecting the Zybo

1. Set `FEED_HOST` in `config.py` to the Zybo's IP address.
2. On the Zybo PS, bind a UDP socket on port `5000` to receive QUOTE frames.
3. TCP connect to the PC on port `5001` to send ORDER frames and receive FILL frames.

See `zybo/protocol.h` for C struct definitions and `zybo/ps_example.c` for a minimal PS skeleton.

## Wire protocol

All frames are big-endian. Prices are fixed-point: `uint32 = round(price × 10000)`.

```
QUOTE  (28 B, UDP)  u8 type | u8 sym | u16 pad | u64 ts_us | u32 bid | u32 ask | u32 bid_sz | u32 ask_sz
ORDER  (18 B, TCP)  u8 type | u8 sym | u8 side | u8 ord_type | u32 id | u32 qty | u32 limit_px | u16 pad
FILL   (14 B, TCP)  u8 type | u8 status | u32 id | u32 fill_qty | u32 fill_px
```

## Configuration

All tunable parameters live in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `FEED_HOST` | `127.0.0.1` | UDP destination (set to Zybo IP for hardware) |
| `FEED_INTERVAL_MS` | `100` | Price update cadence |
| `SYNTHETIC_START_PRICE` | `470.00` | GBM starting price |
| `SYNTHETIC_VOLATILITY` | `0.0003` | Sigma per tick (~30% annualised) |
| `SYNTHETIC_SPREAD_BPS` | `2` | Bid/ask spread in basis points |
| `FILL_LATENCY_MS_MIN/MAX` | `5 / 50` | Simulated OMS round-trip latency |
| `REJECTION_RATE` | `0.02` | Fraction of orders randomly rejected |
| `SLIPPAGE_BPS` | `1` | Market order slippage |
