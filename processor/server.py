"""
Order Management System (OMS) server.

Accepts binary ORDER frames from Zybo over TCP.
Responds with FILL frames on the same connection.

The UI submits orders via submit_order_direct() (same-process call) so
that manual trades follow the same matching path without needing a
loopback TCP connection.
"""

import socket
import threading
from common.protocol import (decode_order, encode_fill,
                             ORDER_SIZE, STATUS_FILLED, STATUS_REJECTED)
from processor.order import Fill, Order, OrderStatus, OrderType, Side
from processor.order_book import OrderBook
from config import OMS_HOST, OMS_PORT, SYMBOL

SYMBOL_ID_MAP = {0: SYMBOL}


class ProcessorServer:
    def __init__(self, fill_queue):
        self._fill_queue = fill_queue
        self._book = OrderBook(self._on_fill)
        self._zybo_conns: dict[int, socket.socket] = {}  # order_id → conn
        self._lock = threading.Lock()

    # ── Quote feed → keep order book current ─────────────────────────────────
    def update_quote(self, bid: float, ask: float):
        self._book.update_quote(bid, ask)

    # ── UI path (same process) ────────────────────────────────────────────────
    def submit_order_direct(self, order: Order):
        self._book.submit(order)

    def cancel_order(self, order_id: int) -> bool:
        return self._book.cancel(order_id)

    def resting_orders(self) -> list[Order]:
        return self._book.resting_orders

    # ── Fill callback (called from OrderBook thread) ──────────────────────────
    def _on_fill(self, fill: Fill):
        # Notify UI
        self._fill_queue.put({
            'order_id': fill.order_id,
            'symbol':   fill.symbol,
            'side':     'BUY' if fill.side == Side.BUY else 'SELL',
            'fill_qty': fill.fill_qty,
            'fill_px':  fill.fill_px,
            'status':   fill.status.name,
        })

        # Respond to Zybo over TCP if order came from hardware
        with self._lock:
            conn = self._zybo_conns.pop(fill.order_id, None)
        if conn:
            status_byte = STATUS_FILLED if fill.status == OrderStatus.FILLED else STATUS_REJECTED
            frame = encode_fill(status_byte, fill.order_id, fill.fill_qty, fill.fill_px)
            try:
                conn.sendall(frame)
            except OSError:
                pass

    # ── Zybo TCP listener ─────────────────────────────────────────────────────
    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((OMS_HOST, OMS_PORT))
        srv.listen(5)
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=self._handle_client,
                             args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket):
        try:
            while True:
                data = self._recv_exact(conn, ORDER_SIZE)
                if not data:
                    break
                raw = decode_order(data)
                order = Order(
                    order_id=raw['order_id'],
                    symbol=SYMBOL_ID_MAP.get(raw['sym_id'], SYMBOL),
                    side=Side(raw['side']),
                    order_type=OrderType(raw['order_type']),
                    qty=raw['qty'],
                    limit_px=raw['limit_px'],
                    source='ZYBO',
                )
                with self._lock:
                    self._zybo_conns[order.order_id] = conn
                self._book.submit(order)
        except OSError:
            pass
        finally:
            conn.close()

    @staticmethod
    def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
        buf = b''
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf
