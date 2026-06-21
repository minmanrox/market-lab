from dataclasses import dataclass
from enum import IntEnum


class Side(IntEnum):
    BUY  = 0
    SELL = 1


class OrderType(IntEnum):
    MARKET = 0
    LIMIT  = 1


class OrderStatus(IntEnum):
    PENDING   = 0
    FILLED    = 1
    PARTIAL   = 2
    REJECTED  = 3
    CANCELLED = 4


@dataclass
class Order:
    order_id:   int
    symbol:     str
    side:       Side
    order_type: OrderType
    qty:        int
    limit_px:   float = 0.0
    status:     OrderStatus = OrderStatus.PENDING
    source:     str = 'UI'   # 'UI' | 'ZYBO'


@dataclass
class Fill:
    order_id:  int
    symbol:    str
    side:      Side
    fill_qty:  int
    fill_px:   float
    status:    OrderStatus
