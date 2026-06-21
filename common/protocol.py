"""
Wire protocol — fixed-width binary frames, big-endian (network byte order).

All prices are stored as uint32 fixed-point: px_int = round(price * PRICE_SCALE).
This avoids floating-point on the PL and makes C struct mapping trivial on the PS.

Frame layout summary (suitable for C struct definitions on Zybo):

  QUOTE  (28 B, UDP)  : u8 type | u8 sym | u16 pad | u64 ts_us | u32 bid | u32 ask | u32 bid_sz | u32 ask_sz
  TRADE  (20 B, UDP)  : u8 type | u8 sym | u16 pad | u64 ts_us | u32 price | u32 size
  ORDER  (18 B, TCP)  : u8 type | u8 sym | u8 side | u8 ord_type | u32 id | u32 qty | u32 limit_px | u16 pad
  FILL   (14 B, TCP)  : u8 type | u8 status | u32 id | u32 fill_qty | u32 fill_px
"""

import struct
import time

# ── Message type tags ────────────────────────────────────────────────────────
MSG_QUOTE     = 0x01
MSG_TRADE     = 0x02
MSG_NEW_ORDER = 0x10
MSG_CANCEL    = 0x11
MSG_FILL      = 0x20

# ── Field constants ──────────────────────────────────────────────────────────
SIDE_BUY  = 0
SIDE_SELL = 1

ORDER_MARKET = 0
ORDER_LIMIT  = 1

STATUS_FILLED   = 0
STATUS_PARTIAL  = 1
STATUS_REJECTED = 2

PRICE_SCALE = 10_000   # store price * 10000 as uint32 → 4 decimal places

# ── Struct formats (! = big-endian, no alignment padding) ───────────────────
QUOTE_FMT = "!BBHQIIII"   # 28 bytes
TRADE_FMT = "!BBHQII"     # 20 bytes
ORDER_FMT = "!BBBBIIIH"   # 18 bytes
FILL_FMT  = "!BBIII"      # 14 bytes

QUOTE_SIZE = struct.calcsize(QUOTE_FMT)
TRADE_SIZE = struct.calcsize(TRADE_FMT)
ORDER_SIZE = struct.calcsize(ORDER_FMT)
FILL_SIZE  = struct.calcsize(FILL_FMT)

# ── Helpers ──────────────────────────────────────────────────────────────────
def px_encode(price: float) -> int:
    return round(price * PRICE_SCALE)

def px_decode(px_int: int) -> float:
    return px_int / PRICE_SCALE

def now_us() -> int:
    return int(time.time() * 1_000_000)

# ── Encoders ─────────────────────────────────────────────────────────────────
def encode_quote(sym_id: int, bid: float, ask: float,
                 bid_sz: int, ask_sz: int) -> bytes:
    return struct.pack(QUOTE_FMT,
        MSG_QUOTE, sym_id, 0, now_us(),
        px_encode(bid), px_encode(ask), bid_sz, ask_sz)

def encode_trade(sym_id: int, price: float, size: int) -> bytes:
    return struct.pack(TRADE_FMT,
        MSG_TRADE, sym_id, 0, now_us(), px_encode(price), size)

def encode_order(sym_id: int, side: int, order_type: int,
                 order_id: int, qty: int, limit_px: float = 0.0) -> bytes:
    return struct.pack(ORDER_FMT,
        MSG_NEW_ORDER, sym_id, side, order_type,
        order_id, qty, px_encode(limit_px), 0)

def encode_fill(status: int, order_id: int,
                fill_qty: int, fill_px: float) -> bytes:
    return struct.pack(FILL_FMT,
        MSG_FILL, status, order_id, fill_qty, px_encode(fill_px))

# ── Decoders ─────────────────────────────────────────────────────────────────
def decode_quote(data: bytes) -> dict:
    _, sym_id, _, ts, bid, ask, bid_sz, ask_sz = struct.unpack(QUOTE_FMT, data)
    return {'type': 'QUOTE', 'sym_id': sym_id, 'ts_us': ts,
            'bid': px_decode(bid), 'ask': px_decode(ask),
            'bid_sz': bid_sz, 'ask_sz': ask_sz}

def decode_trade(data: bytes) -> dict:
    _, sym_id, _, ts, price, size = struct.unpack(TRADE_FMT, data)
    return {'type': 'TRADE', 'sym_id': sym_id, 'ts_us': ts,
            'price': px_decode(price), 'size': size}

def decode_order(data: bytes) -> dict:
    _, sym_id, side, order_type, order_id, qty, limit_px, _ = \
        struct.unpack(ORDER_FMT, data)
    return {'type': 'NEW_ORDER', 'sym_id': sym_id, 'side': side,
            'order_type': order_type, 'order_id': order_id,
            'qty': qty, 'limit_px': px_decode(limit_px)}

def decode_fill(data: bytes) -> dict:
    _, status, order_id, fill_qty, fill_px = struct.unpack(FILL_FMT, data)
    return {'type': 'FILL', 'status': status, 'order_id': order_id,
            'fill_qty': fill_qty, 'fill_px': px_decode(fill_px)}
