from __future__ import annotations

from typing import Any


def _is_rank_candidate(
    *,
    score: int,
    signal_evidence: set[str],
    lexical_evidence: set[str],
) -> bool:
    if score < 4 and not signal_evidence:
        return False
    return bool(signal_evidence or lexical_evidence)


def build_ranked_output(
    *,
    snapshot: Any,
    file_scores: Any,
    evidence: dict[str, set[str]],
    top_n: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path, score in file_scores.most_common(max(1, top_n * 2)):
        component = snapshot.component_for_path(path)
        if not component:
            continue
        signal_evidence = {
            item
            for item in evidence[path]
            if item.startswith("hint:") or item.startswith("component:") or item.startswith("descriptor:")
        }
        lexical_evidence = {
            item
            for item in evidence[path]
            if item.startswith("path:") or item.startswith("symbol:")
        }
        if not _is_rank_candidate(
            score=int(score),
            signal_evidence=signal_evidence,
            lexical_evidence=lexical_evidence,
        ):
            continue
        out.append(
            {
                "path": path,
                "score": int(score),
                "component": component,
                "evidence": sorted(evidence[path])[:10],
            }
        )
        if len(out) >= max(1, top_n):
            break
    return out
