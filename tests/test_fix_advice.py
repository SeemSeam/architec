from __future__ import annotations

import json

from architec.fix_advice.public import build_fix_advice, run_fix_advice


def _review() -> dict[str, object]:
    return {
        "mode": "code_review",
        "review_type": "full",
        "concerns": [
            {
                "concern_id": "code-review:cleanup:1",
                "kind": "cleanup",
                "location": {"path": "src/legacy.py", "line": 0, "symbol": "", "symbol_kind": "module"},
                "evidence": ["cleanup.category=legacy"],
            },
            {
                "concern_id": "code-review:hotspot:1",
                "kind": "hotspot",
                "location": {"path": "src/core.py", "line": 0, "symbol": "", "symbol_kind": "module"},
                "evidence": ["hotspot.rank=1"],
            },
        ],
    }


def test_build_fix_advice_generates_suggestions_from_concerns() -> None:
    result = build_fix_advice(_review(), source_review="review.json")

    assert result["mode"] == "fix_advice"
    assert result["source_review"] == "review.json"
    assert result["summary"] == {
        "headline": "Fix advice generated from review concerns.",
        "suggestion_total": 2,
        "source_concern_total": 2,
    }
    assert result["suggestions"][0]["target"] == "src/legacy.py"
    assert result["suggestions"][0]["concern"] == "code-review:cleanup:1"
    assert "patch" not in json.dumps(result).lower()
    assert "apply" not in json.dumps(result).lower()


def test_build_fix_advice_filters_by_kind_and_file() -> None:
    result = build_fix_advice(_review(), focus_kind="hotspot", focus_file="core")

    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["concern"] == "code-review:hotspot:1"


def test_build_fix_advice_handles_empty_or_missing_evidence() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:boundary:1",
                "kind": "boundary",
                "location": {"path": "src/api.py"},
                "evidence": [],
            }
        ]
    }

    result = build_fix_advice(review)

    assert result["suggestions"][0]["options"] == ["insufficient_evidence_for_fix_advice"]
    assert "guesswork" in result["suggestions"][0]["risks"][0]


def test_run_fix_advice_reads_review_json(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review()), encoding="utf-8")

    result = run_fix_advice(review_path, concern_id="code-review:cleanup:1")

    assert result["source_review"] == str(review_path)
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["target"] == "src/legacy.py"
