"""
Simulated matching engine / order book.

Supported order types:
  MARKET — fills immediately at best available price + slippage
  LIMIT  — fills immediately if the price crosses the limit, otherwise
            rests in the book and is checked on every quote update

Real exchanges also support IOC, FOK, stop orders, etc.; those are future work.

Fill latency and rejection are injected here to make the simulation feel
realistic even when the feed and OMS run on the same machine.
"""

import random
import threading
import time
from typing import Optional

from processor.order import Fill, Order, OrderStatus, OrderType, Side
from config import (FILL_LATENCY_MS_MIN, FILL_LATENCY_MS_MAX,
                    REJECTION_RATE, SLIPPAGE_BPS)


class OrderBook:
    def __init__(self, fill_callback):
        self._bid = 0.0
        self._ask = 0.0
        self._callback = fill_callback
        self._resting: list[Order] = []   # limit orders waiting for price
        self._lock = threading.Lock()

    # ── Quote updates ─────────────────────────────────────────────────────────
    def update_quote(self, bid: float, ask: float):
        self._bid = bid
        self._ask = ask
        self._check_resting()

    def _check_resting(self):
        with self._lock:
            still_resting = []
            for order in self._resting:
                fill_px = self._fill_price(order)
                if fill_px is not None:
                    self._callback(Fill(order.order_id, order.symbol, order.side,
                                       order.qty, fill_px, OrderStatus.FILLED))
                else:
                    still_resting.append(order)
            self._resting = still_resting

    # ── Order submission ──────────────────────────────────────────────────────
    def submit(self, order: Order):
        """Non-blocking — processing happens in a background thread."""
        threading.Thread(target=self._process, args=(order,), daemon=True).start()

    def _process(self, order: Order):
        latency = random.uniform(FILL_LATENCY_MS_MIN, FILL_LATENCY_MS_MAX) / 1000.0
        time.sleep(latency)

        if random.random() < REJECTION_RATE:
            self._callback(Fill(order.order_id, order.symbol, order.side,
                                0, 0.0, OrderStatus.REJECTED))
            return

        fill_px = self._fill_price(order)

        if fill_px is not None:
            self._callback(Fill(order.order_id, order.symbol, order.side,
                                order.qty, fill_px, OrderStatus.FILLED))
        else:
            # Limit order can't cross the current spread — add to resting book
            with self._lock:
                self._resting.append(order)

    # ── Price calculation ─────────────────────────────────────────────────────
    def _fill_price(self, order: Order) -> Optional[float]:
        slip = SLIPPAGE_BPS / 10_000

        if order.order_type == OrderType.MARKET:
            if order.side == Side.BUY:
                return round(self._ask * (1 + slip), 4)
            else:
                return round(self._bid * (1 - slip), 4)

        # LIMIT order
        if order.side == Side.BUY and self._ask <= order.limit_px:
            # Fill at the better of ask or limit (price improvement)
            return round(min(self._ask, order.limit_px), 4)
        if order.side == Side.SELL and self._bid >= order.limit_px:
            return round(max(self._bid, order.limit_px), 4)

        return None   # can't fill yet

    @property
    def resting_orders(self) -> list[Order]:
        with self._lock:
            return list(self._resting)

    def cancel(self, order_id: int) -> bool:
        with self._lock:
            before = len(self._resting)
            self._resting = [o for o in self._resting if o.order_id != order_id]
            return len(self._resting) < before
