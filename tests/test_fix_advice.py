from __future__ import annotations

import json

import pytest
from architec.fix_advice.public import FixAdviceInputError, build_fix_advice, run_fix_advice


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


def test_build_fix_advice_uses_structured_duplication_reference() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:1",
                "kind": "duplication",
                "location": {
                    "path": "src/b.py",
                    "line": 8,
                    "symbol": "second",
                    "symbol_kind": "function",
                },
                "evidence": ["near_duplicate.fingerprint=abc"],
                "references": [
                    {
                        "role": "reference",
                        "path": "src/a.py",
                        "line": 2,
                        "symbol": "first",
                        "symbol_kind": "function",
                    }
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    assert suggestion["target"] == "src/b.py"
    rendered = json.dumps(suggestion)
    assert "src/b.py:8:second" in rendered
    assert "src/a.py:2:first" in rendered
    assert "Normalized AST similarity does not prove semantic equivalence." in suggestion["risks"]


def test_build_fix_advice_duplication_without_reference_stays_advisory() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:2",
                "kind": "duplication",
                "location": {"path": "src/b.py", "line": 8, "symbol": "second"},
                "evidence": ["near_duplicate.fingerprint=abc"],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    assert "Identify the matching implementation" in suggestion["options"][1]
    assert "Evidence does not identify a reference implementation" in suggestion["tradeoffs"][0]


def test_build_fix_advice_duplication_falls_back_to_reference_evidence_string() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:3",
                "kind": "duplication",
                "location": {"path": "src/b.py", "line": 8, "symbol": "second"},
                "evidence": ["near_duplicate.reference=src/a.py:2:first"],
            }
        ]
    }

    result = build_fix_advice(review)

    rendered = json.dumps(result["suggestions"][0])
    assert "src/a.py:2:first" in rendered


def test_fix_advice_duplication_output_avoids_execution_and_gate_terms() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:1",
                "kind": "duplication",
                "location": {"path": "src/b.py", "line": 8, "symbol": "second"},
                "evidence": ["near_duplicate.reference=src/a.py:2:first"],
            }
        ]
    }

    payload = json.dumps(build_fix_advice(review), sort_keys=True).lower()

    assert "patch" not in payload
    assert "apply" not in payload
    assert "must-fix" not in payload
    assert "verdict" not in payload
    assert "pass" not in payload
    assert "fail" not in payload
    assert "block" not in payload


def test_run_fix_advice_reads_review_json(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review()), encoding="utf-8")

    result = run_fix_advice(review_path, concern_id="code-review:cleanup:1")

    assert result["source_review"] == str(review_path)
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["target"] == "src/legacy.py"


def test_run_fix_advice_missing_review_json_raises_input_error(tmp_path) -> None:
    with pytest.raises(FixAdviceInputError, match="Review JSON not found"):
        run_fix_advice(tmp_path / "missing-review.json")


def test_run_fix_advice_invalid_review_json_raises_input_error(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(FixAdviceInputError, match="Invalid review JSON"):
        run_fix_advice(review_path)


def test_run_fix_advice_non_object_review_json_raises_input_error(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(FixAdviceInputError, match="Review JSON must be an object"):
        run_fix_advice(review_path)


def test_run_fix_advice_empty_concerns_is_normal_result(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"mode": "code_review", "concerns": []}), encoding="utf-8")

    result = run_fix_advice(review_path)

    assert result["mode"] == "fix_advice"
    assert result["summary"]["suggestion_total"] == 0
    assert result["suggestions"] == []


def test_run_fix_advice_does_not_write_review_event(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review()), encoding="utf-8")

    run_fix_advice(review_path)

    assert not (tmp_path / ".architec" / "review-events.jsonl").exists()
