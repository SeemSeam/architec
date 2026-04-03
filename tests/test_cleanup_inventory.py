from __future__ import annotations

import json

from architec.cleanup.inventory import build_cleanup_inventory, build_cleanup_ledger
from architec.cleanup.report import render_cleanup_summary, write_cleanup_artifacts


def test_build_cleanup_inventory_detects_heuristic_candidates(tmp_path) -> None:
    (tmp_path / "src" / "legacy").mkdir(parents=True)
    (tmp_path / "tools").mkdir(parents=True)
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "prompts").mkdir(parents=True)
    (tmp_path / "src" / "legacy" / "service.py").write_text("def run():\n    return 'legacy implementation'\n", encoding="utf-8")
    (tmp_path / "tools" / "migration_oneoff.py").write_text("print('temporary script')\n", encoding="utf-8")
    (tmp_path / "docs" / "legacy-migration.md").write_text("Deprecated old flow\n", encoding="utf-8")
    (tmp_path / "config" / "legacy.toml").write_text("# temporary override\n", encoding="utf-8")
    (tmp_path / "prompts" / "legacy-review.md").write_text("Legacy prompt for migration\n", encoding="utf-8")

    inventory = build_cleanup_inventory(tmp_path)
    categories = {item["category"] for item in inventory["candidates"]}

    assert inventory["candidate_total"] >= 4
    assert "legacy_impl" in categories
    assert "obsolete_script" in categories
    assert "stale_doc" in categories
    assert "stale_config" in categories
    assert "stale_prompt" in categories


def test_write_cleanup_artifacts_emits_inventory_ledger_and_summary(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow\n", encoding="utf-8")

    artifact_paths = write_cleanup_artifacts(tmp_path)

    inventory_path = tmp_path / ".architec" / "architec-cleanup-inventory.json"
    ledger_path = tmp_path / ".architec" / "architec-cleanup-ledger.json"
    summary_path = tmp_path / ".architec" / "architec-cleanup-summary.md"
    assert artifact_paths["cleanup_inventory_json"] == str(inventory_path)
    assert artifact_paths["cleanup_ledger_json"] == str(ledger_path)
    assert artifact_paths["cleanup_summary_md"] == str(summary_path)
    assert inventory_path.exists()
    assert ledger_path.exists()
    assert summary_path.exists()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["counts"]["candidate_total"] >= 1
    assert "Cleanup Summary" in summary_path.read_text(encoding="utf-8")


def test_render_cleanup_summary_handles_empty_inventory() -> None:
    inventory = {"candidates": []}
    ledger = {"counts": {"candidate_total": 0, "review_required_total": 0, "by_category": {}}}

    summary = render_cleanup_summary(inventory, ledger)

    assert "No cleanup candidates detected" in summary


def test_build_cleanup_ledger_counts_categories() -> None:
    ledger = build_cleanup_ledger(
        {
            "candidates": [
                {"path": "docs/legacy.md", "kind": "doc", "category": "stale_doc", "confidence": 0.8, "review_required": True},
                {"path": "tools/legacy.py", "kind": "script", "category": "obsolete_script", "confidence": 0.7, "review_required": True},
            ]
        }
    )

    assert ledger["counts"]["candidate_total"] == 2
    assert ledger["counts"]["by_kind"]["doc"] == 1
    assert ledger["counts"]["by_category"]["obsolete_script"] == 1


def test_build_cleanup_inventory_applies_owner_ttl_and_expires_metadata(tmp_path) -> None:
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow\n", encoding="utf-8")
    (tmp_path / "config" / "legacy.toml").write_text("# temporary override\n", encoding="utf-8")
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.cleanup_metadata]]",
                'path = "docs/legacy.md"',
                'owner = "docs-team"',
                "ttl_days = 21",
                'expires_at = "2099-01-01"',
                "",
                "[[archi.cleanup_metadata]]",
                'path = "config/legacy.toml"',
                'owner = "runtime"',
                'expires_at = "2000-01-01"',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    inventory = build_cleanup_inventory(tmp_path)
    ledger = build_cleanup_ledger(inventory)
    items = {item["path"]: item for item in inventory["candidates"]}

    assert items["docs/legacy.md"]["owner"] == "docs-team"
    assert items["docs/legacy.md"]["ttl_days"] == 21
    assert items["docs/legacy.md"]["expires_at"] == "2099-01-01"
    assert items["docs/legacy.md"]["expired"] is False
    assert items["config/legacy.toml"]["owner"] == "runtime"
    assert items["config/legacy.toml"]["expires_at"] == "2000-01-01"
    assert items["config/legacy.toml"]["expired"] is True
    assert ledger["counts"]["owner_total"] == 2
    assert ledger["counts"]["ttl_total"] == 1
    assert ledger["counts"]["expires_total"] == 2
    assert ledger["counts"]["expired_total"] == 1
    assert ledger["counts"]["by_owner"] == {"docs-team": 1, "runtime": 1}
