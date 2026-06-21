#!/usr/bin/env python3
"""
Market Lab — top-level launcher.

Starts all three components in daemon threads, then runs Flask in the
main thread (which blocks until Ctrl-C).

Usage:
  python run.py                  # synthetic GBM prices
  python run.py --csv data.csv   # replay historical CSV (Yahoo Finance format)
"""

import argparse
import queue
import threading

from config import UI_PORT
from feed.server import FeedServer
from processor.server import ProcessorServer
from ui.app import create_app


def main():
    parser = argparse.ArgumentParser(description='Market Lab Simulator')
    parser.add_argument('--csv', metavar='FILE',
                        help='Historical OHLCV CSV for price replay (Yahoo Finance format)')
    args = parser.parse_args()

    feed_queue = queue.Queue(maxsize=500)   # price updates → UI
    fill_queue = queue.Queue(maxsize=500)   # execution reports → UI

    processor = ProcessorServer(fill_queue)
    feed = FeedServer(feed_queue, quote_callback=processor.update_quote)

    if args.csv:
        feed.use_csv(args.csv)
        print(f'[feed]      historical replay: {args.csv}')
    else:
        print('[feed]      synthetic GBM prices')

    threading.Thread(target=processor.run, daemon=True, name='processor').start()
    threading.Thread(target=feed.run,      daemon=True, name='feed').start()

    app, socketio = create_app(feed_queue, fill_queue, processor)

    print(f'[processor] listening on TCP :{5001}')
    print(f'[feed]      broadcasting UDP  :{5000}')
    print(f'[ui]        http://localhost:{UI_PORT}')
    print()

    socketio.run(app, host='0.0.0.0', port=UI_PORT,
                 use_reloader=False, log_output=False,
                 allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
