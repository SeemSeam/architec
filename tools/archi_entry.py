#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    src_text = str(src)
    if src_text in sys.path:
        sys.path.remove(src_text)
    sys.path.insert(0, src_text)
    from architec.cli import main as _main

    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
