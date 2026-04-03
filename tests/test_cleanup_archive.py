from __future__ import annotations

from architec.cleanup.archive import build_archive_candidates


def test_build_archive_candidates_derives_non_source_archive_subset() -> None:
    archive_candidates = build_archive_candidates(
        {
            "candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.73,
                    "evidence": ["content:legacy"],
                    "replacement": "",
                    "review_required": True,
                    "owner": "docs-team",
                    "ttl_days": 14,
                    "expires_at": "2099-01-01",
                    "expired": False,
                },
                {
                    "path": "config/legacy.toml",
                    "kind": "config",
                    "category": "stale_config",
                    "confidence": 0.73,
                    "evidence": ["content:legacy"],
                    "replacement": "",
                    "review_required": True,
                },
                {
                    "path": "src/legacy/core.py",
                    "kind": "source",
                    "category": "legacy_impl",
                    "confidence": 0.73,
                    "evidence": ["content:deprecated"],
                    "replacement": "",
                    "review_required": True,
                },
            ]
        }
    )

    assert archive_candidates["candidate_total"] == 2
    assert archive_candidates["ready_total"] == 1
    assert archive_candidates["review_total"] == 1
    assert archive_candidates["by_category"] == {"stale_config": 1, "stale_doc": 1}
    assert archive_candidates["candidates"][0]["archive_tier"] == "ready"
    assert archive_candidates["candidates"][0]["archive_path_hint"].startswith("archive/")
    assert archive_candidates["candidates"][0]["owner"] == "docs-team"
    assert archive_candidates["candidates"][0]["ttl_days"] == 14
    assert archive_candidates["candidates"][0]["expires_at"] == "2099-01-01"
