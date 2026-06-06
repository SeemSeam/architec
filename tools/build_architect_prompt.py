#!/usr/bin/env python3
"""Build a single architect prompt artifact from templates + snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(_read(path))


def _resolve_default_path(value: str | None, fallback: Path) -> Path:
    return Path(value).resolve() if value else fallback


def _bundle_dir(root: Path) -> Path:
    canonical = root / ".hippos"
    if canonical.exists() or not (root / ".hippocampus").exists():
        return canonical
    return root / ".hippocampus"


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return _load_json(path)
    except Exception:
        return {}


def _structure_excerpt(path: Path, *, max_chars: int) -> str:
    if not path.exists():
        return ""
    structure_text = _read(path)
    if max_chars > 0 and len(structure_text) > max_chars:
        return structure_text[:max_chars] + "\n... (truncated)"
    return structure_text


def _format_top_findings(findings: list[dict[str, Any]], limit: int = 30) -> str:
    ordered = sorted(
        findings,
        key=lambda f: (
            SEVERITY_RANK.get(str(f.get("severity", "info")), 9),
            str(f.get("dimension", "")),
            str(f.get("path", "")),
        ),
    )
    lines: list[str] = []
    for f in ordered[:limit]:
        sev = str(f.get("severity", "info")).upper()
        dim = str(f.get("dimension", "unknown"))
        path = str(f.get("path", "<unknown>"))
        symbol = str(f.get("symbol", "")).strip()
        metric = str(f.get("metric", "")).strip()
        value = f.get("value")
        threshold = f.get("threshold")
        msg = str(f.get("message", ""))
        head = f"- [{sev}] ({dim}) {path}"
        if symbol:
            head += f" :: {symbol}"
        lines.append(head)
        extra = []
        if metric:
            extra.append(f"metric={metric}")
        if value is not None:
            extra.append(f"value={value}")
        if threshold is not None:
            extra.append(f"threshold={threshold}")
        if msg:
            extra.append(f"message={msg}")
        if extra:
            lines.append(f"  - {' | '.join(extra)}")
    if not lines:
        return "- No findings"
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve()
    role_root = here.parents[1]

    p = argparse.ArgumentParser(description="Build architect prompt artifact")
    p.add_argument("--root", default=".", help="Project root")
    p.add_argument("--system-prompt", default=str(role_root / "prompts" / "system.md"))
    p.add_argument("--task-prompt", default=str(role_root / "prompts" / "analyze.md"))
    p.add_argument("--metrics", default=None, help="Metrics JSON path")
    p.add_argument("--rubric", default=None, help="Rubric JSON path")
    p.add_argument("--structure", default=None, help="Structure prompt markdown path")
    p.add_argument("--out", default=None, help="Output markdown path")
    p.add_argument("--structure-chars", type=int, default=12000)
    return p.parse_args()


def _resolve_runtime_paths(args: argparse.Namespace, role_root: Path, root: Path) -> dict[str, Path]:
    bundle_dir = _bundle_dir(root)
    return {
        "metrics": _resolve_default_path(
            args.metrics,
            bundle_dir / "architect-metrics.json",
        ),
        "rubric": _resolve_default_path(
            args.rubric,
            role_root / "config" / "rubric.json",
        ),
        "structure": _resolve_default_path(
            args.structure,
            bundle_dir / "structure-prompt.md",
        ),
        "out": _resolve_default_path(
            args.out,
            bundle_dir / "architect-prompt.md",
        ),
    }


def _prompt_sections(
    *,
    root: Path,
    metrics: dict[str, Any],
    rubric: dict[str, Any],
    system_prompt: str,
    task_prompt: str,
    structure_text: str,
    metrics_path: Path,
) -> list[str]:
    scores = metrics.get("scores", {})
    summary = metrics.get("summary", {})
    findings = metrics.get("findings", [])
    top_findings_md = _format_top_findings(findings)
    out: list[str] = []
    out.append("# Architect Runtime Prompt")
    out.append("")
    out.append("## System Prompt")
    out.append(system_prompt)
    out.append("")
    out.append("## Task Prompt")
    out.append(task_prompt)
    out.append("")
    out.append("## Snapshot Summary")
    out.append(f"- root: `{root}`")
    out.append(f"- generated_at: `{metrics.get('generated_at', '')}`")
    out.append(f"- scores: `{json.dumps(scores, ensure_ascii=False)}`")
    out.append(f"- summary: `{json.dumps(summary, ensure_ascii=False)}`")
    out.append("")
    out.append("## Top Findings")
    out.append(top_findings_md)
    out.append("")
    out.append("## Rubric Thresholds")
    if rubric:
        out.append(f"- weights: `{json.dumps(rubric.get('weights', {}), ensure_ascii=False)}`")
        out.append(
            f"- thresholds: `{json.dumps(rubric.get('thresholds', {}), ensure_ascii=False)}`"
        )
        layer_contracts = rubric.get("layer_contracts", [])
        if isinstance(layer_contracts, list) and layer_contracts:
            out.append(
                f"- layer_contracts: `{json.dumps(layer_contracts, ensure_ascii=False)}`"
            )
    else:
        out.append("(rubric not found)")
    out.append("")
    out.append("## Structure Prompt (Excerpt)")
    if structure_text.strip():
        out.append("```markdown")
        out.append(structure_text.strip())
        out.append("```")
    else:
        out.append("(structure prompt not found)")
    out.append("")
    out.append("## Full Metrics Path")
    out.append(f"- `{metrics_path}`")
    return out


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    runtime_paths = _resolve_runtime_paths(args, role_root, root)
    metrics_path = runtime_paths["metrics"]
    rubric_path = runtime_paths["rubric"]
    structure_path = runtime_paths["structure"]
    out_path = runtime_paths["out"]

    if not metrics_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {metrics_path}")

    metrics = _load_json(metrics_path)
    system_prompt = _read(Path(args.system_prompt).resolve()).strip()
    task_prompt = _read(Path(args.task_prompt).resolve()).strip()
    structure_text = _structure_excerpt(structure_path, max_chars=args.structure_chars)
    rubric = _optional_json(rubric_path)
    out = _prompt_sections(
        root=root,
        metrics=metrics,
        rubric=rubric,
        system_prompt=system_prompt,
        task_prompt=task_prompt,
        structure_text=structure_text,
        metrics_path=metrics_path,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"Wrote prompt: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
