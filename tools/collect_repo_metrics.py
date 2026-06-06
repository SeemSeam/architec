#!/usr/bin/env python3
"""Collect architecture metrics for the standalone architect role."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_repo_metrics_runtime import (
    accumulate_scan_counters,
    analyze_file_metrics,
    apply_layer_contracts,
)
from collect_repo_metrics_rules import load_architecture_rules
from collect_repo_metrics_scan import (
    iter_files,
)


LANG_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "shell",
    ".zsh": "shell",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
}
_BUNDLE_FINGERPRINT_FILES = (
    "hippos-index.json",
    "code-signatures.json",
    "file-manifest.json",
)
_LEGACY_BUNDLE_FINGERPRINT_FILES = (
    "hippocampus-index.json",
    "code-signatures.json",
    "file-manifest.json",
)


@dataclass
class Thresholds:
    line_soft: int
    line_hard: int
    module_soft: int
    module_hard: int
    cc_soft: int
    cc_hard: int
    class_methods_soft: int
    class_attrs_soft: int


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle_fingerprint(root: Path) -> str:
    hasher = hashlib.sha256()
    included = 0
    bundle_dir = root / ".hippos"
    names = _BUNDLE_FINGERPRINT_FILES
    if not bundle_dir.exists() and (root / ".hippocampus").exists():
        bundle_dir = root / ".hippocampus"
        names = _LEGACY_BUNDLE_FINGERPRINT_FILES
    for name in names:
        path = bundle_dir / name
        if not path.exists() or not path.is_file():
            continue
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
        included += 1
    if included <= 0:
        return ""
    return hasher.hexdigest()


def _detect_lang(path: Path) -> str:
    return LANG_BY_EXT.get(path.suffix.lower(), "other")


def _score_from_findings(
    weights: dict[str, float],
    findings: list[dict[str, Any]],
    total_files: int,
) -> dict[str, float]:
    dims = ["file_structure", "file_size", "code_style", "encapsulation", "complexity"]
    scores: dict[str, float] = {d: 10.0 for d in dims}

    severity_weight = {
        "critical": 3.0,
        "warning": 1.0,
        "info": 0.25,
    }
    weighted_counts: dict[str, float] = defaultdict(float)

    for f in findings:
        dim = f.get("dimension")
        sev = f.get("severity", "info")
        if dim in scores:  # type: ignore[operator]
            weighted_counts[str(dim)] += severity_weight.get(str(sev), 0.25)

    norm = max(1.0, math.sqrt(float(max(total_files, 1))))
    for d in dims:
        # Log penalty avoids collapsing large repos to near-zero score.
        scaled = weighted_counts[d] / norm
        penalty = min(9.0, math.log2(1.0 + scaled))
        scores[d] = max(1.0, round(10.0 - penalty, 2))

    overall = 0.0
    for d in dims:
        overall += scores[d] * float(weights.get(d, 0.2))
    scores["overall"] = round(overall, 2)
    return scores


def collect_metrics(root: Path, rubric: dict[str, Any]) -> dict[str, Any]:
    thresholds = rubric.get("thresholds", {})
    thr = Thresholds(
        line_soft=int(thresholds.get("line_length", {}).get("soft", 100)),
        line_hard=int(thresholds.get("line_length", {}).get("hard", 120)),
        module_soft=int(thresholds.get("module_lines", {}).get("soft", 300)),
        module_hard=int(thresholds.get("module_lines", {}).get("hard", 1000)),
        cc_soft=int(thresholds.get("cyclomatic_complexity", {}).get("soft", 10)),
        cc_hard=int(thresholds.get("cyclomatic_complexity", {}).get("hard", 15)),
        class_methods_soft=int(thresholds.get("class_public_methods", {}).get("soft", 20)),
        class_attrs_soft=int(thresholds.get("class_instance_attributes", {}).get("soft", 7)),
    )

    exclude_dirs = set(rubric.get("exclude_dirs", []))
    exclude_suffixes = set(rubric.get("exclude_suffixes", []))
    files = iter_files(
        root,
        exclude_dirs,
        exclude_suffixes,
        rules=load_architecture_rules(root),
    )

    findings: list[dict[str, Any]] = []
    ext_counter: Counter[str] = Counter()
    lang_counter: Counter[str] = Counter()
    file_rows: list[dict[str, Any]] = []
    line_over_soft = 0
    line_over_hard = 0
    py_imports: dict[str, set[str]] = {}
    py_function_count = 0
    py_class_count = 0

    for p in files:
        entry = analyze_file_metrics(path=p, root=root, thr=thr, detect_lang=_detect_lang)
        if entry is None:
            continue
        accumulate_scan_counters(entry=entry, ext_counter=ext_counter, lang_counter=lang_counter)
        file_rows.append(
            {
                "path": entry["path"],
                "lang": entry["lang"],
                "lines": entry["lines"],
                "bytes": entry["bytes"],
            }
        )
        findings.extend(entry["findings"])
        line_over_soft += int(entry["line_soft_hits"])
        line_over_hard += int(entry["line_hard_hits"])

        py_result = entry["py_result"]
        if not isinstance(py_result, dict):
            continue
        py_imports[entry["path"]] = py_result["imports"]
        py_function_count += int(py_result["function_count"])
        py_class_count += int(py_result["class_count"])

    findings.extend(
        apply_layer_contracts(
            rubric=rubric,
            py_imports=py_imports,
            file_rows=file_rows,
        )
    )

    weights = rubric.get("weights", {})
    scores = _score_from_findings(weights, findings, total_files=len(file_rows))

    file_rows.sort(key=lambda x: (x["lines"], x["bytes"]), reverse=True)
    top_large_files = file_rows[:20]

    findings_by_sev = Counter(f["severity"] for f in findings)
    findings_by_dim = Counter(f.get("dimension", "other") for f in findings)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "bundle_fingerprint": _bundle_fingerprint(root),
        "summary": {
            "total_files": len(file_rows),
            "total_lines": sum(x["lines"] for x in file_rows),
            "languages": dict(lang_counter.most_common()),
            "extensions": dict(ext_counter.most_common()),
            "python_functions": py_function_count,
            "python_classes": py_class_count,
            "line_over_soft": line_over_soft,
            "line_over_hard": line_over_hard,
        },
        "thresholds": {
            "line_length": {"soft": thr.line_soft, "hard": thr.line_hard},
            "module_lines": {"soft": thr.module_soft, "hard": thr.module_hard},
            "cyclomatic_complexity": {"soft": thr.cc_soft, "hard": thr.cc_hard},
            "class_public_methods": {"soft": thr.class_methods_soft},
            "class_instance_attributes": {"soft": thr.class_attrs_soft},
        },
        "scores": scores,
        "file_structure": {
            "largest_files": top_large_files,
        },
        "findings_stats": {
            "by_severity": dict(findings_by_sev),
            "by_dimension": dict(findings_by_dim),
            "total": len(findings),
        },
        "findings": findings,
    }


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve()
    default_rubric = here.parents[1] / "config" / "rubric.json"

    p = argparse.ArgumentParser(description="Collect repo architecture metrics")
    p.add_argument("--root", default=".", help="Project root")
    p.add_argument("--rubric", default=str(default_rubric), help="Rubric JSON path")
    p.add_argument("--out", default=None, help="Output JSON path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    rubric_path = Path(args.rubric).resolve()
    rubric = _load_json(rubric_path)

    out_path = Path(args.out).resolve() if args.out else root / ".hippos" / "architect-metrics.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = collect_metrics(root, rubric)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote metrics: {out_path}")
    print(f"Overall score: {result['scores']['overall']}")
    print(f"Total findings: {result['findings_stats']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
