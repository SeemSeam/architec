from __future__ import annotations

from collections import Counter

_LOW_SIGNAL_SYMBOLS = {
    "__init__",
    "__enter__",
    "__exit__",
    "init",
    "main",
    "run",
    "open",
    "close",
    "handle",
    "process",
    "execute",
    "helper",
    "get",
    "set",
    "load",
    "save",
}


def collect_component_symbols(snapshot, files: list[str]) -> list[str]:
    counter = Counter()
    quality: dict[str, tuple[int, int]] = {}
    for path in files:
        for sig in snapshot.signatures_for_file(path):
            name = str(sig.get("name", "") or "").strip()
            rank = symbol_rank(name)
            if rank <= 0:
                continue
            counter[name] += 1
            quality[name] = max(quality.get(name, (0, 0)), (rank, len(name)))
    ranked = sorted(
        counter.items(),
        key=lambda item: (
            -quality.get(item[0], (0, 0))[0],
            -item[1],
            -quality.get(item[0], (0, 0))[1],
            item[0],
        ),
    )
    return [name for name, _ in ranked[:16]]


def _is_low_signal_symbol(text: str) -> bool:
    if text in _LOW_SIGNAL_SYMBOLS or len(text) < 4:
        return True
    leaf = text.rsplit(".", 1)[-1].lower()
    return leaf in _LOW_SIGNAL_SYMBOLS and "." not in text


def _symbol_rank_bonus(text: str, leaf: str) -> int:
    rank = 1
    if "." in text:
        rank += 4
    if any(ch.isupper() for ch in text):
        rank += 2
    if "_" in text and not text.startswith("_"):
        rank += 1
    if len(text) >= 12:
        rank += 1
    if leaf in _LOW_SIGNAL_SYMBOLS:
        rank -= 1
    return rank


def symbol_rank(name: str) -> int:
    text = str(name or "").strip()
    if not text or text.startswith("test_") or _is_low_signal_symbol(text):
        return 0
    leaf = text.rsplit(".", 1)[-1].lower()
    return max(0, _symbol_rank_bonus(text, leaf))


def findings_by_severity(findings: list[dict[str, object]]) -> dict[str, int]:
    counts = Counter()
    for item in findings:
        counts[str(item.get("severity", "info") or "info").lower()] += 1
    return {key: int(counts.get(key, 0)) for key in ("critical", "warning", "info")}
