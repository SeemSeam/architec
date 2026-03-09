from __future__ import annotations

import time
from typing import Any


def timed_step(label: str, fn) -> tuple[Any, dict[str, Any]]:
    started = time.perf_counter()
    result = fn()
    elapsed = round(time.perf_counter() - started, 3)
    return result, {"label": label, "elapsed_sec": elapsed, "ok": True}
