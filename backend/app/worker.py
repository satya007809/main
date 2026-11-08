"""Standalone background worker: `python -m app.worker` (run one or more alongside the API)."""
import logging
import signal

from .jobs.queue import WorkerThread
from .main import init_db

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    w = WorkerThread()
    signal.signal(signal.SIGTERM, lambda *_: w.stop_event.set())
    w.start()
    try:
        while w.is_alive():
            w.join(1)
    except KeyboardInterrupt:
        w.stop_event.set()
