from __future__ import annotations

import argparse
import time
from pathlib import Path

from packages.worker_engine import DurableTaskQueue


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai-control-plane-worker")
    parser.add_argument("--db", default=".ai-control-plane/tasks.db")
    parser.add_argument("--worker-id", default="worker-1")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    queue = DurableTaskQueue(Path(args.db))
    while True:
        task = queue.lease(args.worker_id)
        if task is None:
            if args.once:
                return
            time.sleep(1)
            continue
        try:
            # Execution adapters are registered by deployments; the base worker
            # records a successful no-op for unknown task types rather than running arbitrary commands.
            queue.complete(task.id, args.worker_id)
        except Exception as exc:  # pragma: no cover - defensive worker boundary
            queue.fail(task.id, args.worker_id, str(exc))
        if args.once:
            return


if __name__ == "__main__":
    main()
