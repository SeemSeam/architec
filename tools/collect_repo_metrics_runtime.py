from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from collect_repo_metrics_python import analyze_python_file
from collect_repo_metrics_scan import (
    is_probably_binary,
    line_length_summary,
    module_size_findings,
    safe_read,
)


def analyze_file_metrics(*, path: Path, root: Path, thr, detect_lang) -> dict[str, Any] | None:
    if is_probably_binary(path):
        return None

    rel = path.relative_to(root).as_posix()
    text = safe_read(path)
    lines = text.splitlines()
    line_count = len(lines)
    lang = detect_lang(path)

    findings = module_size_findings(rel=rel, line_count=line_count, thr=thr)
    line_summary = line_length_summary(rel=rel, lines=lines, thr=thr)
    findings.extend(line_summary["findings"])

    py_result = None
    if lang == "python":
        py_result = analyze_python_file(rel=rel, text=text, thr=thr)
        findings.extend(py_result["findings"])

    return {
        "path": rel,
        "lang": lang,
        "ext": path.suffix.lower(),
        "lines": line_count,
        "bytes": path.stat().st_size,
        "findings": findings,
        "line_soft_hits": int(line_summary["soft_hits"]),
        "line_hard_hits": int(line_summary["hard_hits"]),
        "py_result": py_result,
    }


def apply_layer_contracts(
    *,
    rubric: dict[str, Any],
    py_imports: dict[str, set[str]],
    file_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    top_prefixes = {row["path"].split("/", 1)[0] for row in file_rows}
    for contract in rubric.get("layer_contracts", []):
        from_prefix = str(contract.get("from_prefix", ""))
        allowed = [str(x) for x in contract.get("allowed_to_prefixes", [])]
        severity = str(contract.get("severity", "warning"))
        if not from_prefix:
            continue
        for path, imports in py_imports.items():
            if not path.startswith(from_prefix):
                continue
            for root_name in sorted(imports):
                candidate_prefix = f"{root_name}/"
                if root_name not in top_prefixes or candidate_prefix in allowed:
                    continue
                findings.append(
                    {
                        "id": "layer_contract_violation",
                        "dimension": "file_structure",
                        "severity": severity,
                        "path": path,
                        "metric": "layer_contract",
                        "value": candidate_prefix,
                        "threshold": allowed,
                        "message": "Import may violate configured layer contract.",
                    }
                )
    return findings


def accumulate_scan_counters(
    *,
    entry: dict[str, Any],
    ext_counter: Counter[str],
    lang_counter: Counter[str],
) -> None:
    ext_counter[entry["ext"] or "<none>"] += 1
    lang_counter[entry["lang"]] += 1

