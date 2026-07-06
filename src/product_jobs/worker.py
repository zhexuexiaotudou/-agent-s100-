from __future__ import annotations

import argparse
import time
from pathlib import Path

from .queue import ProductJobQueue


def main() -> int:
    parser = argparse.ArgumentParser(description="Digua AI product job worker placeholder.")
    parser.add_argument("--db-path", type=Path, default=Path("reports/product_jobs/runtime/product_jobs.db"))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    queue = ProductJobQueue(args.db_path)
    print(queue.status(), flush=True)
    if args.once:
        return 0
    while True:
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
