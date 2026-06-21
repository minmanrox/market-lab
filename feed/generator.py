"""
Synthetic price generator using Geometric Brownian Motion.

GBM is the standard model underlying Black-Scholes option pricing.
Each tick: S(t+dt) = S(t) * exp(sigma * sqrt(dt) * Z),  Z ~ N(0,1)
No drift term — we're simulating intraday noise, not long-run returns.
"""

import math
import random
from config import (SYNTHETIC_START_PRICE, SYNTHETIC_VOLATILITY,
                    SYNTHETIC_SPREAD_BPS, FEED_INTERVAL_MS)


class SyntheticGenerator:
    def __init__(self):
        self.mid = SYNTHETIC_START_PRICE
        self._dt = FEED_INTERVAL_MS / 1000.0

    def next_quote(self) -> tuple[float, float, int, int]:
        z = random.gauss(0, 1)
        self.mid *= math.exp(SYNTHETIC_VOLATILITY * math.sqrt(self._dt) * z)

        half_spread = self.mid * SYNTHETIC_SPREAD_BPS / 20_000  # /2 then /10000
        bid = round(self.mid - half_spread, 4)
        ask = round(self.mid + half_spread, 4)

        # Size randomised around a base lot — roughly mimics L1 quote sizes
        bid_sz = random.randint(100, 2000)
        ask_sz = random.randint(100, 2000)
        return bid, ask, bid_sz, ask_sz
