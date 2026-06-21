"""
Historical CSV replay — supports Yahoo Finance OHLCV format.

Download QQQ data from Yahoo Finance (daily or intraday):
  https://finance.yahoo.com/quote/QQQ/history

Expected columns (case-insensitive): Date, Open, High, Low, Close, Volume
Bid/ask are synthesised from the close price + configured spread, since
Yahoo doesn't provide L1 quote data. Each row = one feed tick.

The replay loops forever when it reaches the end of the file so the
simulator never runs out of data during a long session.
"""

import csv
import random
from config import SYNTHETIC_SPREAD_BPS


class CsvReplay:
    def __init__(self, csv_path: str):
        self._rows = self._load(csv_path)
        self._idx = 0
        if not self._rows:
            raise ValueError(f"No usable rows found in {csv_path}")

    def _load(self, path: str) -> list[dict]:
        rows = []
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            # Normalise header names to lowercase
            for raw in reader:
                row = {k.strip().lower(): v.strip() for k, v in raw.items()}
                try:
                    close = float(row.get('close') or row.get('adj close') or 0)
                    volume = int(float(row.get('volume') or 0))
                    if close > 0:
                        rows.append({'close': close, 'volume': volume})
                except (ValueError, TypeError):
                    continue
        return rows

    def next_quote(self) -> tuple[float, float, int, int]:
        row = self._rows[self._idx % len(self._rows)]
        self._idx += 1

        mid = row['close']
        half_spread = mid * SYNTHETIC_SPREAD_BPS / 20_000
        bid = round(mid - half_spread, 4)
        ask = round(mid + half_spread, 4)

        # Spread daily volume across ~3900 ticks (6.5 h × 600 ticks/h at 100 ms cadence)
        base_sz = max(100, row['volume'] // 3900)
        bid_sz = random.randint(base_sz // 2, base_sz * 2)
        ask_sz = random.randint(base_sz // 2, base_sz * 2)
        return bid, ask, bid_sz, ask_sz

    @property
    def symbol_hint(self) -> str:
        return "CSV"
