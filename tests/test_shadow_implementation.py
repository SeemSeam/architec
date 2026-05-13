from __future__ import annotations

import json

import architec.code_review.public as code_review
from architec.code_review.shadow_implementation import shadow_implementation_concerns


def _empty_report() -> dict[str, object]:
    return {
        "scores": {},
        "summary": {},
        "cleanup": {},
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [],
        "topology": {},
        "artifacts": {},
    }


def _write_shadow_policy_project(tmp_path) -> None:
    policy_dir = tmp_path / "src" / "policy"
    policy_dir.mkdir(parents=True)
    (policy_dir / "base_policy.py").write_text(
        """
def component_allow_policy(component, rules, context):
    allowed = []
    denied = []
    for rule in rules:
        if rule.get("disabled"):
            continue
        target = rule.get("component")
        if target not in ("*", component):
            continue
        decision = rule.get("decision")
        if decision == "allow":
            allowed.append(rule.get("name", ""))
        elif decision == "deny":
            denied.append(rule.get("name", ""))
    if context.get("maintenance"):
        denied.append("maintenance")
    if context.get("owner") == component:
        allowed.append("owner")
    return bool(allowed) and not denied
""",
        encoding="utf-8",
    )
    (policy_dir / "generated_policy.py").write_text(
        """
def component_permission_policy(component, rules, context):
    matches = []
    warnings = []
    for entry in rules:
        active = not entry.get("disabled")
        if not active:
            continue
        matches_scope = entry.get("component") in ("*", component)
        if not matches_scope:
            continue
        value = entry.get("decision")
        if value == "allow":
            matches.append(entry.get("name", ""))
        if value == "deny":
            warnings.append(entry.get("name", ""))
    if context.get("maintenance"):
        warnings.append("maintenance")
    if context.get("owner") == component:
        matches.append("owner")
    return len(matches) > 0 and len(warnings) == 0
""",
        encoding="utf-8",
    )
    (policy_dir / "extra_policy.py").write_text(
        """
def component_access_policy(component, rules, context):
    accepted = []
    rejected = []
    for item in rules:
        if item.get("disabled"):
            continue
        scope = item.get("component")
        if scope != "*" and scope != component:
            continue
        marker = item.get("decision")
        if marker == "allow":
            accepted.append(item.get("name", ""))
        elif marker == "deny":
            rejected.append(item.get("name", ""))
    if context.get("maintenance") is True:
        rejected.append("maintenance")
    owner = context.get("owner")
    if owner == component:
        accepted.append("owner")
    return len(accepted) >= 1 and len(rejected) == 0
""",
        encoding="utf-8",
    )


def test_shadow_implementation_concerns_detect_policy_like_functions(tmp_path) -> None:
    _write_shadow_policy_project(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns
    concern = concerns[0]
    assert concern["kind"] == "shadow-implementation"
    assert concern["concern_id"].startswith("code-review:shadow-implementation:")
    assert concern["location"]["path"].startswith("src/policy/")
    assert concern["location"]["symbol_kind"] == "function"
    assert concern["references"] == [
        {
            "role": "existing_implementation",
            "path": "src/policy/base_policy.py",
            "line": 2,
            "symbol": "component_allow_policy",
            "symbol_kind": "function",
        }
    ]
    assert "shadow_implementation.role=policy" in concern["evidence"]
    assert "shadow_implementation.reuse_edge=false" in concern["evidence"]
    assert all(not item.startswith("Add ") for item in concern["evidence"])


def test_shadow_implementation_concern_id_is_stable(tmp_path) -> None:
    _write_shadow_policy_project(tmp_path)

    first = shadow_implementation_concerns(tmp_path)
    second = shadow_implementation_concerns(tmp_path)

    assert [item["concern_id"] for item in first] == [item["concern_id"] for item in second]


def test_shadow_implementation_ignores_exact_near_duplicate_pair(tmp_path) -> None:
    (tmp_path / "a_policy.py").write_text(
        """
def component_allow_policy(component, rules, context):
    total = 0
    for item in rules:
        if item.get("decision") == "allow":
            total += 1
        else:
            total += 2
    if context.get("enabled"):
        total += 3
    if component:
        total += 4
    return total > 5
""",
        encoding="utf-8",
    )
    (tmp_path / "b_policy.py").write_text(
        """
def component_permission_policy(service, entries, metadata):
    result = 0
    for row in entries:
        if row.get("mode") == "yes":
            result += 1
        else:
            result += 2
    if metadata.get("flag"):
        result += 3
    if service:
        result += 4
    return result > 5
""",
        encoding="utf-8",
    )

    assert shadow_implementation_concerns(tmp_path) == []


def test_shadow_implementation_ignores_delegating_wrapper(tmp_path) -> None:
    (tmp_path / "base_policy.py").write_text(
        """
def component_allow_policy(component, rules, context):
    allowed = []
    denied = []
    for rule in rules:
        if rule.get("disabled"):
            continue
        target = rule.get("component")
        if target not in ("*", component):
            continue
        decision = rule.get("decision")
        if decision == "allow":
            allowed.append(rule.get("name", ""))
        elif decision == "deny":
            denied.append(rule.get("name", ""))
    if context.get("maintenance"):
        denied.append("maintenance")
    if context.get("owner") == component:
        allowed.append("owner")
    return bool(allowed) and not denied
""",
        encoding="utf-8",
    )
    (tmp_path / "candidate_policy.py").write_text(
        """
from base_policy import component_allow_policy


def component_permission_policy(component, rules, context):
    normalized = []
    for rule in rules:
        if rule.get("disabled"):
            continue
        target = rule.get("component")
        if target not in ("*", component):
            continue
        normalized.append(rule)
    if context.get("owner") == component:
        normalized.append({"component": component, "decision": "allow", "name": "owner"})
    if context.get("maintenance"):
        normalized.append({"component": component, "decision": "deny", "name": "maintenance"})
    return component_allow_policy(component, normalized, context)
""",
        encoding="utf-8",
    )

    assert shadow_implementation_concerns(tmp_path) == []


def test_shadow_implementation_ignores_small_report_helpers(tmp_path) -> None:
    (tmp_path / "a_report.py").write_text(
        """
def _report_section(title, lines):
    rows = [title]
    rows.extend(lines)
    return "\\n".join(rows)
""",
        encoding="utf-8",
    )
    (tmp_path / "b_report.py").write_text(
        """
def _report_chunk(title, lines):
    result = [title]
    result.extend(lines)
    return "\\n".join(result)
""",
        encoding="utf-8",
    )

    assert shadow_implementation_concerns(tmp_path) == []


def test_code_review_full_includes_shadow_signal_and_concern(tmp_path, monkeypatch) -> None:
    _write_shadow_policy_project(tmp_path)
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_report())

    result = code_review.run_code_review_full(tmp_path)

    concern = next(item for item in result["concerns"] if item["kind"] == "shadow-implementation")
    assert concern["references"][0]["role"] == "existing_implementation"
    signal = next(item for item in result["signals"] if item["kind"] == "shadow_implementation")
    assert signal["metrics"] == {
        "candidate_total": 3,
        "high_confidence_total": 3,
        "by_role": {"policy": 3},
    }


def test_code_review_diff_and_since_do_not_include_shadow_signal(tmp_path, monkeypatch) -> None:
    _write_shadow_policy_project(tmp_path)
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_report())

    diff_result = code_review.run_code_review_diff(tmp_path)
    since_result = code_review.run_code_review_since(tmp_path, ref="main")

    assert all(item["kind"] != "shadow-implementation" for item in diff_result["concerns"])
    assert all(item["kind"] != "shadow-implementation" for item in since_result["concerns"])
    assert all(item["kind"] != "shadow_implementation" for item in diff_result["signals"])
    assert all(item["kind"] != "shadow_implementation" for item in since_result["signals"])


def test_shadow_implementation_output_avoids_gate_and_repair_terms(tmp_path) -> None:
    _write_shadow_policy_project(tmp_path)

    payload = json.dumps(shadow_implementation_concerns(tmp_path), sort_keys=True).lower()

    forbidden = (
        "pa" + "ss",
        "fa" + "il",
        "blo" + "ck",
        "ver" + "dict",
        "must" + "-fix",
        "pa" + "tch",
        "ap" + "ply",
    )
    for term in forbidden:
        assert term not in payload
