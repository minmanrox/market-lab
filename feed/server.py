"""
Market Feed Server — broadcasts binary QUOTE frames over UDP.

In a real exchange this corresponds to a multicast market-data feed
(NASDAQ ITCH, NYSE OpenBook, etc.).  The Zybo listens on FEED_PORT
and parses the binary frames directly.

quote_callback is wired to the OMS so the order book stays current,
and to the UI bridge so the dashboard updates in real-time.
"""

import socket
import time
from common.protocol import encode_quote
from feed.generator import SyntheticGenerator
from config import FEED_HOST, FEED_PORT, FEED_INTERVAL_MS, SYMBOL

SYMBOL_ID = 0   # QQQ = sym_id 0 on the wire


class FeedServer:
    def __init__(self, feed_queue, quote_callback=None):
        self._queue = feed_queue
        self._quote_callback = quote_callback   # called with (bid, ask) each tick
        self._source = SyntheticGenerator()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._running = False

    def use_csv(self, path: str):
        from feed.replay import CsvReplay
        self._source = CsvReplay(path)

    def run(self):
        self._running = True
        interval = FEED_INTERVAL_MS / 1000.0

        while self._running:
            t0 = time.monotonic()

            bid, ask, bid_sz, ask_sz = self._source.next_quote()

            # ── Zybo wire ────────────────────────────────────────────────────
            frame = encode_quote(SYMBOL_ID, bid, ask, bid_sz, ask_sz)
            try:
                self._sock.sendto(frame, (FEED_HOST, FEED_PORT))
            except OSError:
                pass

            # ── Internal callbacks ────────────────────────────────────────────
            if self._quote_callback:
                self._quote_callback(bid, ask)

            msg = {
                'sym': SYMBOL,
                'bid': bid, 'ask': ask,
                'mid': round((bid + ask) / 2, 4),
                'bid_sz': bid_sz, 'ask_sz': ask_sz,
            }
            try:
                self._queue.put_nowait(msg)
            except Exception:
                pass  # queue full — drop stale quote, UI will catch next one

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, interval - elapsed))

    def stop(self):
        self._running = False
        self._sock.close()
