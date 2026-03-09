from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis_cache import run_cached_analysis
from .architecture_report_compaction import (
    compact_batches,
    compact_descriptors,
    compact_hotspots,
    llm_report_payload,
)
from .architecture_report_sections import render_architecture_report_markdown
from .backend_llm import complete_json
from .component_descriptors import load_or_build_component_descriptors
from .hippo_adapter import HippoSnapshot
from .io_utils import utc_now_iso
from .llm_guard import guard_llm_result
from .paths import ARCHITECTURE_REPORT_MD_PATH


def _llm_generate_report(
    root: Path,
    *,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
    prompt = (
        "You are a principal software architect writing a full architecture review report.\n"
        "Return strict JSON only with schema:\n"
        "{\n"
        '  "title":"string",\n'
        '  "executive_summary":"string",\n'
        '  "score_summary":["string"],\n'
        '  "top_hotspots":[{"path":"string","risk":"string","reason":"string"}],\n'
        '  "refactor_plan":[{"priority":"P0|P1|P2","objective":"string","focus_files":["string"],"acceptance":"string"}],\n'
        '  "test_and_risk_control":["string"],\n'
        '  "next_iteration":"string"\n'
        "}\n\n"
        f"Input:\n{payload}"
    )
    llm_doc, cache_hit = run_cached_analysis(
        root,
        namespace="architect_full_report_md",
        payload=payload,
        runner=lambda: guard_llm_result(
            root,
            task="architect_full_report_md",
            runner=lambda: complete_json(
                root,
                task="architect_full_report_md",
                tier="strong",
                prompt=prompt,
                timeout_sec=35.0,
                max_tokens=1600,
                required=True,
            ),
        ),
    )
    return llm_doc, cache_hit


def _resolve_llm_doc(
    root: Path,
    *,
    llm_enabled: bool,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
    if not llm_enabled:
        return None, False
    doc, cache_hit = _llm_generate_report(root, payload=payload)
    if isinstance(doc, dict):
        return doc, cache_hit
    return None, cache_hit


def _build_report_context(
    root: Path,
    *,
    goal: str,
    question: str,
    governance: dict[str, Any],
    hotspot_digest: dict[str, Any],
    batches: list[dict[str, Any]],
    feature: dict[str, Any],
    qa: dict[str, Any],
) -> dict[str, Any]:
    generated_at = utc_now_iso()
    snapshot = HippoSnapshot.load(root)
    descriptor_map = load_or_build_component_descriptors(root, snapshot=snapshot, persist=False)
    descriptors = compact_descriptors(
        descriptor_map,
        batches=batches,
        feature=feature,
        qa=qa,
        limit=6,
    )
    hotspots = compact_hotspots(hotspot_digest, limit=12)
    compacted_batches = compact_batches(batches, limit=12)
    payload = llm_report_payload(
        goal=goal,
        question=question,
        governance=governance,
        hotspot_digest=hotspot_digest,
        batches=batches,
        feature=feature,
        qa=qa,
        descriptors=descriptors,
    )
    return {
        "generated_at": generated_at,
        "descriptors": descriptors,
        "hotspots": hotspots,
        "batches": compacted_batches,
        "payload": payload,
    }


def _persist_report_markdown(root: Path, *, markdown: str) -> Path:
    report_path = root / ARCHITECTURE_REPORT_MD_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")
    return report_path


def write_architecture_report_markdown(
    root: Path,
    *,
    goal: str,
    question: str,
    governance: dict[str, Any],
    hotspot_digest: dict[str, Any],
    batches: list[dict[str, Any]],
    feature: dict[str, Any],
    qa: dict[str, Any],
    llm_enabled: bool,
) -> dict[str, Any]:
    context = _build_report_context(
        root,
        goal=goal,
        question=question,
        governance=governance,
        hotspot_digest=hotspot_digest,
        batches=batches,
        feature=feature,
        qa=qa,
    )

    llm_doc, llm_cache_hit = _resolve_llm_doc(
        root,
        llm_enabled=llm_enabled,
        payload=context["payload"],
    )

    markdown = render_architecture_report_markdown(
        generated_at=str(context["generated_at"]),
        goal=goal,
        question=question,
        governance=governance,
        hotspots=context["hotspots"],
        batches=context["batches"],
        descriptors=context["descriptors"],
        llm_doc=llm_doc,
    )

    report_path = _persist_report_markdown(root, markdown=markdown)
    return {
        "path": str(report_path),
        "generated_at": str(context["generated_at"]),
        "llm_used": bool(llm_doc),
        "llm_cache_hit": llm_cache_hit,
        "llm_model": str((llm_doc or {}).get("_llm_model", "") or ""),
        "llm_provider": str((llm_doc or {}).get("_llm_provider", "") or ""),
    }
