from __future__ import annotations

from architec.cleanup import semantic_judge as semantic


def test_run_semantic_judge_enriches_llm_judgments(tmp_path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "legacy").mkdir(parents=True)
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow for docs\n", encoding="utf-8")
    (tmp_path / "src" / "legacy" / "core.py").write_text(
        "def legacy_core():\n    return 'legacy implementation'\n",
        encoding="utf-8",
    )
    inventory = {
        "candidate_total": 2,
        "candidates": [
            {
                "path": "src/legacy/core.py",
                "kind": "source",
                "category": "legacy_impl",
                "confidence": 0.89,
                "evidence": ["path:legacy", "content:legacy implementation"],
                "replacement": "src/core.py",
                "review_required": True,
                "owner": "core-team",
                "ttl_days": 14,
                "expires_at": "2099-01-01",
                "expired": False,
            },
            {
                "path": "docs/legacy.md",
                "kind": "doc",
                "category": "stale_doc",
                "confidence": 0.81,
                "evidence": ["path:legacy", "content:deprecated"],
                "replacement": "",
                "review_required": True,
                "owner": "docs-team",
                "expires_at": "2000-01-01",
                "expired": True,
            },
        ],
    }
    archive_candidates = {
        "candidate_total": 1,
        "ready_total": 1,
        "review_total": 0,
        "candidates": [
            {
                "path": "docs/legacy.md",
                "kind": "doc",
                "category": "stale_doc",
                "archive_tier": "ready",
                "archive_reason": "stale documentation is safe to archive",
                "archive_path_hint": "archive/docs/legacy.md",
            }
        ],
    }
    monkeypatch.setattr(semantic, "load_cached_analysis", lambda *args, **kwargs: None)
    saved: dict[str, object] = {}
    monkeypatch.setattr(
        semantic,
        "save_cached_analysis",
        lambda root, *, namespace, payload, result: saved.update(
            {
                "namespace": namespace,
                "payload": payload,
                "result": result,
            }
        ),
    )
    monkeypatch.setattr(
        semantic,
        "_llm_semantic_judge",
        lambda root, payload, *, fail_open: {
            "summary": "Reviewed the top cleanup candidates and found one immediate retirement plus one archive-first document.",
            "judgments": [
                {
                    "path": "docs/legacy.md",
                    "decision": "archive_first",
                    "confidence": 0.91,
                    "reason": "stale documentation is low-risk to archive",
                    "archive_path_hint": "archive/docs/legacy.md",
                    "signals": ["stale_doc", "ready_archive"],
                },
                {
                    "path": "src/legacy/core.py",
                    "decision": "retire_now",
                    "confidence": 0.88,
                    "reason": "legacy implementation has a clear replacement",
                    "replacement": "src/core.py",
                    "signals": ["legacy_impl", "replacement"],
                },
            ],
        },
    )

    result = semantic.run_semantic_judge(
        tmp_path,
        cleanup_inventory=inventory,
        archive_candidates=archive_candidates,
        llm_enabled=True,
        fail_open=True,
    )

    assert result["status"] == "ok"
    assert result["candidate_pool_total"] == 2
    assert result["reviewed_total"] == 2
    assert result["by_decision"]["archive_first"] == 1
    assert result["by_decision"]["retire_now"] == 1
    assert result["top_judgments"][0]["decision"] == "retire_now"
    assert result["judgments"][1]["archive_path_hint"] == "archive/docs/legacy.md"
    assert result["judgments"][0]["owner"] == "core-team"
    assert result["judgments"][0]["ttl_days"] == 14
    assert result["judgments"][1]["owner"] == "docs-team"
    assert result["judgments"][1]["expired"] is True
    assert saved["namespace"] == "architect_semantic_judge"


def test_run_semantic_judge_fail_open_marks_unavailable(tmp_path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow\n", encoding="utf-8")
    inventory = {
        "candidate_total": 1,
        "candidates": [
            {
                "path": "docs/legacy.md",
                "kind": "doc",
                "category": "stale_doc",
                "confidence": 0.81,
                "evidence": ["path:legacy"],
                "replacement": "",
                "review_required": True,
            }
        ],
    }
    archive_candidates = {"candidate_total": 0, "candidates": []}
    monkeypatch.setattr(semantic, "load_cached_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        semantic,
        "save_cached_analysis",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not cache unavailable result")),
    )
    monkeypatch.setattr(
        semantic,
        "_llm_semantic_judge",
        lambda root, payload, *, fail_open: {
            "status": "unavailable",
            "error_type": "ArchitectLLMUnavailableError",
            "error": "no backend LLM candidate configured",
        },
    )

    result = semantic.run_semantic_judge(
        tmp_path,
        cleanup_inventory=inventory,
        archive_candidates=archive_candidates,
        llm_enabled=True,
        fail_open=True,
    )

    assert result["status"] == "unavailable"
    assert result["reviewed_total"] == 0
    assert result["error_type"] == "ArchitectLLMUnavailableError"
    assert "no backend LLM candidate configured" in result["error"]
