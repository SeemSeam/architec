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
    policy_dir.mkdir(parents=True, exist_ok=True)
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


def _write_shadow_policy_classes(tmp_path) -> None:
    policy_dir = tmp_path / "src" / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "base_class.py").write_text(
        """
class ComponentPolicyReviewer:
    def __init__(self, rules, defaults, audit_log):
        self.rules = list(rules)
        self.defaults = dict(defaults)
        self.audit_log = audit_log

    def collect_allowed_components(self, component, context):
        allowed = []
        denied = []
        for rule in self.rules:
            if rule.get("disabled"):
                continue
            target = rule.get("component", "*")
            if target not in ("*", component):
                continue
            decision = rule.get("decision", self.defaults.get(target, "deny"))
            if decision == "allow":
                allowed.append(rule.get("name", target))
            elif decision == "deny":
                denied.append(rule.get("name", target))
        if context.get("maintenance"):
            denied.append("maintenance")
        if context.get("owner") == component:
            allowed.append("owner")
        return allowed, denied

    def is_component_allowed(self, component, context):
        allowed, denied = self.collect_allowed_components(component, context)
        self.audit_log.append({"component": component, "allowed": len(allowed), "denied": len(denied)})
        return bool(allowed) and not denied

    def explain_component_policy(self, component, context):
        allowed, denied = self.collect_allowed_components(component, context)
        notes = []
        for name in allowed:
            notes.append(f"allow:{name}")
        for name in denied:
            notes.append(f"deny:{name}")
        return notes
""",
        encoding="utf-8",
    )
    (policy_dir / "candidate_class.py").write_text(
        """
class ComponentPolicyInspector:
    def __init__(self, rules, defaults, events):
        self.entries = list(rules)
        self.defaults = dict(defaults)
        self.events = events

    def collect_allowed_components(self, component, context):
        accepted = []
        rejected = []
        for entry in self.entries:
            if entry.get("disabled"):
                continue
            scope = entry.get("component", "*")
            if scope != "*" and scope != component:
                continue
            marker = entry.get("decision", self.defaults.get(scope, "deny"))
            if marker == "allow":
                accepted.append(entry.get("name", scope))
            elif marker == "deny":
                rejected.append(entry.get("name", scope))
        if context.get("maintenance"):
            rejected.append("maintenance")
        if context.get("owner") == component:
            accepted.append("owner")
        return accepted, rejected

    def is_component_allowed(self, component, context):
        accepted, rejected = self.collect_allowed_components(component, context)
        self.events.append({"component": component, "allowed": len(accepted), "denied": len(rejected)})
        return len(accepted) > 0 and len(rejected) == 0

    def explain_component_policy(self, component, context):
        accepted, rejected = self.collect_allowed_components(component, context)
        details = []
        for name in accepted:
            details.append(f"allow:{name}")
        for name in rejected:
            details.append(f"deny:{name}")
        return details
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


def test_shadow_implementation_concerns_detect_policy_like_classes(tmp_path) -> None:
    _write_shadow_policy_classes(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)
    concern = next(item for item in concerns if item["location"]["symbol_kind"] == "class")

    assert concern["kind"] == "shadow-implementation"
    assert concern["concern_id"].startswith("code-review:shadow-implementation:")
    assert concern["location"] == {
        "path": "src/policy/candidate_class.py",
        "line": 2,
        "symbol": "ComponentPolicyInspector",
        "symbol_kind": "class",
    }
    assert concern["references"] == [
        {
            "role": "existing_implementation",
            "path": "src/policy/base_class.py",
            "line": 2,
            "symbol": "ComponentPolicyReviewer",
            "symbol_kind": "class",
        }
    ]
    assert "shadow_implementation.scope=class" in concern["evidence"]
    assert any(item.startswith("shadow_implementation.api_similarity=") for item in concern["evidence"])
    assert any(item.startswith("shadow_implementation.member_counts=") for item in concern["evidence"])


def test_shadow_implementation_concern_id_is_stable(tmp_path) -> None:
    _write_shadow_policy_project(tmp_path)

    first = shadow_implementation_concerns(tmp_path)
    second = shadow_implementation_concerns(tmp_path)

    assert [item["concern_id"] for item in first] == [item["concern_id"] for item in second]


def test_shadow_implementation_class_concern_id_is_stable(tmp_path) -> None:
    _write_shadow_policy_classes(tmp_path)

    first = [
        item
        for item in shadow_implementation_concerns(tmp_path)
        if item["location"]["symbol_kind"] == "class"
    ]
    second = [
        item
        for item in shadow_implementation_concerns(tmp_path)
        if item["location"]["symbol_kind"] == "class"
    ]

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


def test_shadow_implementation_ignores_exact_duplicate_class(tmp_path) -> None:
    (tmp_path / "a_policy.py").write_text(
        """
class ComponentPolicyReviewer:
    def __init__(self, rules, defaults):
        self.rules = list(rules)
        self.defaults = dict(defaults)

    def collect_allowed_components(self, component, context):
        allowed = []
        denied = []
        for rule in self.rules:
            if rule.get("disabled"):
                continue
            target = rule.get("component", "*")
            if target not in ("*", component):
                continue
            decision = rule.get("decision", self.defaults.get(target, "deny"))
            if decision == "allow":
                allowed.append(rule.get("name", target))
            elif decision == "deny":
                denied.append(rule.get("name", target))
        if context.get("maintenance"):
            denied.append("maintenance")
        return allowed, denied

    def is_component_allowed(self, component, context):
        allowed, denied = self.collect_allowed_components(component, context)
        return bool(allowed) and not denied
""",
        encoding="utf-8",
    )
    (tmp_path / "b_policy.py").write_text(
        """
class ComponentPolicyInspector:
    def __init__(self, entries, fallback):
        self.entries = list(entries)
        self.fallback = dict(fallback)

    def collect_allowed_components(self, service, metadata):
        matches = []
        warnings = []
        for item in self.entries:
            if item.get("disabled"):
                continue
            target = item.get("component", "*")
            if target not in ("*", service):
                continue
            decision = item.get("decision", self.fallback.get(target, "deny"))
            if decision == "allow":
                matches.append(item.get("name", target))
            elif decision == "deny":
                warnings.append(item.get("name", target))
        if metadata.get("maintenance"):
            warnings.append("maintenance")
        return matches, warnings

    def is_component_allowed(self, service, metadata):
        matches, warnings = self.collect_allowed_components(service, metadata)
        return bool(matches) and not warnings
""",
        encoding="utf-8",
    )

    concerns = shadow_implementation_concerns(tmp_path)

    assert all(item["location"]["symbol_kind"] != "class" for item in concerns)


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


def test_shadow_implementation_ignores_delegating_wrapper_class(tmp_path) -> None:
    _write_shadow_policy_classes(tmp_path)
    (tmp_path / "src" / "policy" / "adapter_class.py").write_text(
        """
from base_class import ComponentPolicyReviewer


class ComponentPolicyAdapter:
    def __init__(self, rules, defaults, audit_log):
        self.reviewer = ComponentPolicyReviewer(rules, defaults, audit_log)

    def collect_allowed_components(self, component, context):
        return self.reviewer.collect_allowed_components(component, context)

    def is_component_allowed(self, component, context):
        return self.reviewer.is_component_allowed(component, context)

    def explain_component_policy(self, component, context):
        return self.reviewer.explain_component_policy(component, context)
""",
        encoding="utf-8",
    )

    concerns = shadow_implementation_concerns(tmp_path)

    assert all(item["location"]["path"] != "src/policy/adapter_class.py" for item in concerns)


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


def test_shadow_implementation_ignores_small_class(tmp_path) -> None:
    (tmp_path / "a_policy.py").write_text(
        """
class ComponentPolicyOne:
    def __init__(self, value):
        self.value = value

    def is_component_allowed(self, component):
        return component == self.value
""",
        encoding="utf-8",
    )
    (tmp_path / "b_policy.py").write_text(
        """
class ComponentPolicyTwo:
    def __init__(self, value):
        self.value = value

    def is_component_allowed(self, component):
        return component == self.value
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
        "by_symbol_kind": {"function": 3},
    }


def test_code_review_full_includes_class_shadow_signal_and_concern(tmp_path, monkeypatch) -> None:
    _write_shadow_policy_classes(tmp_path)
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_report())

    result = code_review.run_code_review_full(tmp_path)

    concern = next(
        item
        for item in result["concerns"]
        if item["kind"] == "shadow-implementation" and item["location"]["symbol_kind"] == "class"
    )
    assert concern["references"][0]["role"] == "existing_implementation"
    signal = next(item for item in result["signals"] if item["kind"] == "shadow_implementation")
    assert signal["metrics"]["by_symbol_kind"]["class"] == 1
    assert signal["metrics"]["candidate_total"] >= 1
    assert signal["metrics"]["high_confidence_total"] >= 1


def test_code_review_diff_and_since_do_not_include_shadow_signal(tmp_path, monkeypatch) -> None:
    _write_shadow_policy_project(tmp_path)
    _write_shadow_policy_classes(tmp_path)
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
