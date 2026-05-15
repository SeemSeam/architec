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


def test_build_fix_advice_duplication_keeps_reference_role_semantics() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:role-check",
                "kind": "duplication",
                "location": {"path": "src/b.py", "line": 8, "symbol": "second"},
                "evidence": ["near_duplicate.fingerprint=abc"],
                "references": [
                    {
                        "role": "existing_implementation",
                        "path": "src/shadow_existing.py",
                        "line": 1,
                        "symbol": "not_dup_reference",
                        "symbol_kind": "function",
                    },
                    {
                        "role": "reference",
                        "path": "src/a.py",
                        "line": 2,
                        "symbol": "first",
                        "symbol_kind": "function",
                    },
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    rendered = json.dumps(result["suggestions"][0])
    assert "src/a.py:2:first" in rendered
    assert "src/shadow_existing.py" not in rendered


def test_build_fix_advice_duplication_uses_compatibility_option_for_legacy_location() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:legacy",
                "kind": "duplication",
                "location": {
                    "path": "src/prompts/legacy_project_prompts_dir.py",
                    "line": 12,
                    "symbol": "legacy_project_prompts_dir",
                    "symbol_kind": "function",
                },
                "evidence": ["near_duplicate.fingerprint=abc"],
                "references": [
                    {
                        "role": "reference",
                        "path": "src/prompts/project.py",
                        "line": 4,
                        "symbol": "project_prompts_dir",
                        "symbol_kind": "function",
                    }
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    rendered = json.dumps(suggestion).lower()
    assert "compare duplicate" in rendered
    assert "compatibility path" in rendered
    assert "compatibility wrapper" in rendered
    assert "legacy_project_prompts_dir" in rendered
    assert "project_prompts_dir" in rendered


def test_build_fix_advice_duplication_without_compatibility_signal_keeps_generic_options() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:ordinary",
                "kind": "duplication",
                "location": {"path": "src/current.py", "line": 8, "symbol": "build_messages"},
                "evidence": ["near_duplicate.fingerprint=abc"],
                "references": [
                    {
                        "role": "reference",
                        "path": "src/shared.py",
                        "line": 2,
                        "symbol": "make_messages",
                        "symbol_kind": "function",
                    }
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    rendered = json.dumps(suggestion).lower()
    assert "routing the duplicate through the reference implementation" in rendered
    assert "compatibility path" not in rendered
    assert "compatibility wrapper" not in rendered


def test_build_fix_advice_duplication_uses_compatibility_option_from_evidence_only() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:evidence-compat",
                "kind": "duplication",
                "location": {"path": "src/current.py", "line": 8, "symbol": "build_messages"},
                "evidence": ["near_duplicate.fingerprint=abc", "near_duplicate.category=compat"],
                "references": [
                    {
                        "role": "reference",
                        "path": "src/shared.py",
                        "line": 2,
                        "symbol": "make_messages",
                        "symbol_kind": "function",
                    }
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    rendered = json.dumps(result["suggestions"][0]).lower()
    assert "compatibility path" in rendered
    assert "compatibility wrapper" in rendered


def test_build_fix_advice_duplication_ignores_existing_implementation_reference_for_compatibility() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:near-duplicate:shadow-role-only",
                "kind": "duplication",
                "location": {"path": "src/legacy_current.py", "line": 8, "symbol": "legacy_current"},
                "evidence": ["near_duplicate.fingerprint=abc"],
                "references": [
                    {
                        "role": "existing_implementation",
                        "path": "src/shared.py",
                        "line": 2,
                        "symbol": "make_messages",
                        "symbol_kind": "function",
                    }
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    rendered = json.dumps(suggestion).lower()
    assert "identify the matching implementation" in rendered
    assert "src/shared.py" not in rendered
    assert "compatibility path" not in rendered


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


def test_build_fix_advice_shadow_function_uses_existing_implementation_reference() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:shadow-implementation:abc123",
                "kind": "shadow-implementation",
                "location": {
                    "path": "src/new_policy.py",
                    "line": 8,
                    "symbol": "component_permission_policy",
                    "symbol_kind": "function",
                },
                "evidence": [
                    "shadow_implementation.role=policy",
                    "shadow_implementation.reuse_edge=false",
                ],
                "references": [
                    {
                        "role": "existing_implementation",
                        "path": "src/base_policy.py",
                        "line": 2,
                        "symbol": "component_allow_policy",
                        "symbol_kind": "function",
                    }
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    rendered = json.dumps(suggestion)
    assert suggestion["target"] == "src/new_policy.py"
    assert "src/new_policy.py:8:component_permission_policy" in rendered
    assert "src/base_policy.py:2:component_allow_policy" in rendered
    assert "routing through" in suggestion["options"][1]
    assert "does not decide which implementation is correct" in suggestion["risks"][1]


def test_build_fix_advice_shadow_class_uses_existing_implementation_reference() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:shadow-implementation:def456",
                "kind": "shadow-implementation",
                "location": {
                    "path": "src/policy/candidate_class.py",
                    "line": 2,
                    "symbol": "ComponentPolicyInspector",
                    "symbol_kind": "class",
                },
                "evidence": [
                    "shadow_implementation.scope=class",
                    "shadow_implementation.role=policy",
                ],
                "references": [
                    {
                        "role": "existing_implementation",
                        "path": "src/policy/base_class.py",
                        "line": 2,
                        "symbol": "ComponentPolicyReviewer",
                        "symbol_kind": "class",
                    }
                ],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    rendered = json.dumps(suggestion)
    assert "Compare class src/policy/candidate_class.py:2:ComponentPolicyInspector" in rendered
    assert "src/policy/base_class.py:2:ComponentPolicyReviewer" in rendered
    assert "extracting shared behavior" in suggestion["options"][1]


def test_build_fix_advice_shadow_without_reference_stays_generic() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:shadow-implementation:no-ref",
                "kind": "shadow-implementation",
                "location": {"path": "src/new_policy.py", "line": 8, "symbol": "component_permission_policy"},
                "evidence": ["shadow_implementation.role=policy"],
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    assert "Identify the existing implementation" in suggestion["options"][1]
    assert "advice stays generic" in suggestion["tradeoffs"][0]


def test_fix_advice_shadow_output_avoids_execution_and_gate_terms() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:shadow-implementation:abc123",
                "kind": "shadow-implementation",
                "location": {"path": "src/new_policy.py", "line": 8, "symbol": "component_permission_policy"},
                "evidence": ["shadow_implementation.role=policy"],
                "references": [
                    {
                        "role": "existing_implementation",
                        "path": "src/base_policy.py",
                        "line": 2,
                        "symbol": "component_allow_policy",
                        "symbol_kind": "function",
                    }
                ],
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


def test_build_fix_advice_architecture_contract_uses_rule_evidence_and_hint() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:architecture-contract:abc123",
                "kind": "architecture-contract",
                "location": {"path": "src/api/handler.py", "line": 1, "symbol": "", "symbol_kind": "module"},
                "evidence": [
                    "architecture_contract.rule_id=api-no-storage",
                    "architecture_contract.source_glob=src/api/**",
                    "architecture_contract.import=app.storage",
                    "architecture_contract.restricted_import=app.storage",
                    "architecture_contract.owner=api-platform",
                ],
                "next_steps_hint": "Use the service facade.",
            }
        ]
    }

    result = build_fix_advice(review)

    suggestion = result["suggestions"][0]
    rendered = json.dumps(suggestion)
    assert suggestion["target"] == "src/api/handler.py"
    assert "src/api/handler.py:1" in rendered
    assert "rule api-no-storage" in rendered
    assert "import app.storage" in rendered
    assert "Use the service facade." in rendered
    assert "owner api-platform" in rendered
    assert "does not decide whether the contract or the changed import" in suggestion["risks"][1]


def test_fix_advice_architecture_contract_output_avoids_execution_and_gate_terms() -> None:
    review = {
        "concerns": [
            {
                "concern_id": "code-review:architecture-contract:abc123",
                "kind": "architecture-contract",
                "location": {"path": "src/api/handler.py", "line": 1, "symbol": "", "symbol_kind": "module"},
                "evidence": [
                    "architecture_contract.rule_id=api-no-storage",
                    "architecture_contract.import=app.storage",
                    "architecture_contract.restricted_import=app.storage",
                ],
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
    assert result["summary"]["headline"] == "No fix advice suggestions were generated for this review."
    assert result["summary"]["reason"] == "The review has no matching concerns for the selected filters."
    assert result["suggestions"] == []
    encoded = json.dumps(result["summary"], sort_keys=True).lower()
    for term in ("pass", "fail", "block", "verdict", "must-fix", "clean", "safe"):
        assert term not in encoded


def test_run_fix_advice_does_not_write_review_event(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review()), encoding="utf-8")

    run_fix_advice(review_path)

    assert not (tmp_path / ".architec" / "review-events.jsonl").exists()
