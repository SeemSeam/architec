from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from architec.integration.hippo_adapter import HippoSnapshot
from architec.support.io_utils import normalize_relpath

SEVERITY_WEIGHT = {
    "critical": 4.0,
    "warning": 1.2,
    "info": 0.15,
}


def finding_key(finding: dict[str, Any]) -> str:
    path = normalize_relpath(str(finding.get("path", "")))
    metric = str(finding.get("metric", "")).strip().lower()
    symbol = str(finding.get("symbol", "")).strip()
    severity = str(finding.get("severity", "")).strip().lower()
    value = str(finding.get("value", "")).strip()
    threshold = str(finding.get("threshold", "")).strip()
    return "|".join([path, metric, symbol, severity, value, threshold])


def aggregate_hotspots(findings: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}

    for f in findings:
        path = normalize_relpath(str(f.get("path", "")))
        if not path:
            continue
        entry = by_path.setdefault(
            path,
            {
                "path": path,
                "score": 0.0,
                "critical": 0,
                "warning": 0,
                "info": 0,
                "metrics": Counter(),
                "dimensions": Counter(),
                "samples": [],
            },
        )
        sev = str(f.get("severity", "info")).lower()
        dim = str(f.get("dimension", "other")).lower()
        metric = str(f.get("metric", "")).lower()
        entry[sev] = int(entry.get(sev, 0)) + 1
        entry["score"] = float(entry.get("score", 0.0)) + SEVERITY_WEIGHT.get(sev, 0.2)
        entry["metrics"][metric] += 1
        entry["dimensions"][dim] += 1

        if len(entry["samples"]) < 4:
            sample = {
                "severity": sev,
                "dimension": dim,
                "metric": metric,
                "symbol": str(f.get("symbol", "")).strip(),
                "message": str(f.get("message", "")).strip(),
                "value": f.get("value"),
                "threshold": f.get("threshold"),
            }
            entry["samples"].append(sample)

    ranked = sorted(by_path.values(), key=lambda x: (-float(x["score"]), -int(x["critical"]), x["path"]))
    out: list[dict[str, Any]] = []
    for item in ranked[: max(1, top_n)]:
        out.append(
            {
                "path": item["path"],
                "score": round(float(item["score"]), 2),
                "critical": int(item["critical"]),
                "warning": int(item["warning"]),
                "info": int(item["info"]),
                "top_metrics": dict(item["metrics"].most_common(5)),
                "top_dimensions": dict(item["dimensions"].most_common(5)),
                "samples": item["samples"],
            }
        )
    return out


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity = Counter()
    by_dimension = Counter()
    by_metric = Counter()

    for f in findings:
        by_severity[str(f.get("severity", "info")).lower()] += 1
        by_dimension[str(f.get("dimension", "other")).lower()] += 1
        by_metric[str(f.get("metric", "unknown")).lower()] += 1

    return {
        "total": len(findings),
        "by_severity": dict(by_severity),
        "by_dimension": dict(by_dimension),
        "by_metric": dict(by_metric.most_common(20)),
    }


def issue_catalog(findings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in findings:
        key = finding_key(f)
        out[key] = {
            "path": normalize_relpath(str(f.get("path", ""))),
            "severity": str(f.get("severity", "info")).lower(),
            "dimension": str(f.get("dimension", "other")).lower(),
            "metric": str(f.get("metric", "unknown")).lower(),
            "symbol": str(f.get("symbol", "")).strip(),
            "message": str(f.get("message", "")).strip(),
            "value": f.get("value"),
            "threshold": f.get("threshold"),
        }
    return out


def build_component_risk(snapshot: HippoSnapshot, findings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    comp: dict[str, dict[str, Any]] = defaultdict(lambda: {"critical": 0, "warning": 0, "info": 0, "score": 0.0, "files": set()})
    for f in findings:
        path = normalize_relpath(str(f.get("path", "")))
        if not path:
            continue
        component = snapshot.component_for_path(path)
        sev = str(f.get("severity", "info")).lower()
        comp_entry = comp[component]
        comp_entry[sev] = int(comp_entry.get(sev, 0)) + 1
        comp_entry["score"] = float(comp_entry.get("score", 0.0)) + SEVERITY_WEIGHT.get(sev, 0.2)
        comp_entry["files"].add(path)

    out: dict[str, dict[str, Any]] = {}
    for k, v in comp.items():
        out[k] = {
            "critical": int(v.get("critical", 0)),
            "warning": int(v.get("warning", 0)),
            "info": int(v.get("info", 0)),
            "risk_score": round(float(v.get("score", 0.0)), 2),
            "file_count": len(v.get("files", set())),
            "files": sorted(v.get("files", set()))[:20],
        }
    return dict(sorted(out.items(), key=lambda kv: (-kv[1]["risk_score"], kv[0])))
