"""
Flask + Flask-SocketIO dashboard server.

Two background threads bridge the internal queues to WebSocket events:
  feed_queue  → 'quote' events  (price updates, bid/ask/mid)
  fill_queue  → 'fill'  events  (execution reports)

P&L is tracked here using the average-cost method.  All accounting is
server-side so the Zybo integration can query portfolio state later via REST.
"""

import queue
import threading
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from config import SYMBOL, UI_PORT
from processor.order import Order, OrderStatus, OrderType, Side


# ── Shared order ID counter ───────────────────────────────────────────────────
_oid = 0
_oid_lock = threading.Lock()

def _next_oid() -> int:
    global _oid
    with _oid_lock:
        _oid += 1
        return _oid


# ── Portfolio tracker (average cost method) ───────────────────────────────────
class PortfolioTracker:
    def __init__(self):
        self.position   = 0
        self.avg_cost   = 0.0
        self.realized   = 0.0
        self.current_mid = 0.0

    @property
    def unrealized(self) -> float:
        # Works for long (positive) and short (negative) positions
        return (self.current_mid - self.avg_cost) * self.position

    @property
    def total(self) -> float:
        return self.realized + self.unrealized

    def on_fill(self, side: str, qty: int, fill_px: float):
        if side == 'BUY':
            if self.position < 0:
                closed = min(qty, -self.position)
                self.realized += (self.avg_cost - fill_px) * closed
            new_pos = self.position + qty
            if new_pos > 0:
                if self.position <= 0:
                    self.avg_cost = fill_px
                else:
                    self.avg_cost = (self.avg_cost * self.position + fill_px * qty) / new_pos
            self.position = new_pos

        else:  # SELL
            if self.position > 0:
                closed = min(qty, self.position)
                self.realized += (fill_px - self.avg_cost) * closed
            new_pos = self.position - qty
            if new_pos < 0:
                if self.position >= 0:
                    self.avg_cost = fill_px
                else:
                    self.avg_cost = (self.avg_cost * abs(self.position) + fill_px * qty) / abs(new_pos)
            self.position = new_pos

    def snapshot(self) -> dict:
        return {
            'position':   self.position,
            'avg_cost':   round(self.avg_cost, 4),
            'unrealized': round(self.unrealized, 2),
            'realized':   round(self.realized, 2),
            'total':      round(self.total, 2),
        }


# ── App factory ───────────────────────────────────────────────────────────────
def create_app(feed_queue: queue.Queue, fill_queue: queue.Queue, processor):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'market-lab-dev'
    socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')
    portfolio = PortfolioTracker()

    # ── Routes ────────────────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return render_template('index.html', symbol=SYMBOL)

    @app.route('/order', methods=['POST'])
    def place_order():
        data = request.json
        oid  = _next_oid()
        order = Order(
            order_id   = oid,
            symbol     = SYMBOL,
            side       = Side.BUY if data['side'] == 'BUY' else Side.SELL,
            order_type = OrderType.MARKET if data['order_type'] == 'MARKET' else OrderType.LIMIT,
            qty        = int(data['qty']),
            limit_px   = float(data.get('limit_px') or 0.0),
            source     = 'UI',
        )
        processor.submit_order_direct(order)
        return jsonify({'order_id': oid, 'status': 'SUBMITTED'})

    @app.route('/cancel', methods=['POST'])
    def cancel_order():
        data = request.json
        ok = processor.cancel_order(int(data['order_id']))
        return jsonify({'cancelled': ok})

    @app.route('/resting')
    def resting():
        orders = processor.resting_orders()
        return jsonify([{
            'order_id': o.order_id,
            'side':     o.side.name,
            'qty':      o.qty,
            'limit_px': o.limit_px,
        } for o in orders])

    @app.route('/portfolio')
    def portfolio_state():
        return jsonify(portfolio.snapshot())

    # ── Background tasks: queue → WebSocket ──────────────────────────────────
    def feed_emitter():
        while True:
            try:
                msg = feed_queue.get(timeout=0.1)
                portfolio.current_mid = msg['mid']
                socketio.emit('quote', {**msg, 'pnl': portfolio.snapshot()})
            except queue.Empty:
                pass

    def fill_emitter():
        while True:
            try:
                fill = fill_queue.get(timeout=0.1)
                if fill['status'] == 'FILLED':
                    portfolio.on_fill(fill['side'], fill['fill_qty'], fill['fill_px'])
                socketio.emit('fill', {**fill, 'pnl': portfolio.snapshot()})
            except queue.Empty:
                pass

    socketio.start_background_task(feed_emitter)
    socketio.start_background_task(fill_emitter)

    return app, socketio
