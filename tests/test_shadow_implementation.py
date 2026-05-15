from __future__ import annotations

import json

import architec.code_review.public as code_review
from architec.code_review.shadow_implementation import (
    shadow_implementation_concerns,
    shadow_implementation_file_dry_run,
)


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


def _write_shadow_policy_project_with_paths(tmp_path, *, existing_path: str, candidate_path: str) -> None:
    existing = tmp_path / existing_path
    candidate = tmp_path / candidate_path
    existing.parent.mkdir(parents=True, exist_ok=True)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text(
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
    candidate.write_text(
        """
def component_permission_policy(component, rules, context):
    matches = []
    warnings = []
    for entry in rules:
        if entry.get("disabled"):
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


def _write_render_assembly_split(tmp_path) -> None:
    source = tmp_path / "src" / "maps"
    source.mkdir(parents=True, exist_ok=True)
    (source / "renderer.py").write_text(
        """
def render_project_map(entries, options, budget):
    lines = []
    for entry in entries:
        name = entry.get("name", "")
        details = entry.get("details", [])
        if not details:
            continue
        row = [name]
        for detail in details:
            row.append(f"- {detail}")
        if options.get("include_budget"):
            row.append(str(budget.get(name, 0)))
        lines.append("\\n".join(row))
    if options.get("footer"):
        lines.append("rendered")
    return "\\n\\n".join(lines)
""",
        encoding="utf-8",
    )
    (source / "assembler.py").write_text(
        """
def append_project_map(entries, options, budget):
    chunks = []
    for entry in entries:
        name = entry.get("name", "")
        details = entry.get("details", [])
        if details == []:
            continue
        chunk = [name]
        for detail in details:
            chunk.append(f"- {detail}")
        if options.get("include_budget") is True:
            chunk.append(str(budget.get(name, 0)))
        chunks.append("\\n".join(chunk))
    if options.get("footer") is True:
        chunks.append("assembled")
    return "\\n\\n".join(chunks)
""",
        encoding="utf-8",
    )


def _write_parser_helpers(tmp_path) -> None:
    source = tmp_path / "src" / "parsers"
    source.mkdir(parents=True, exist_ok=True)
    (source / "block_parser.py").write_text(
        """
def parse_json_block(text, strict=False):
    payload = text.strip()
    if payload.startswith("```"):
        lines = payload.splitlines()
        payload = "\\n".join(lines[1:-1])
    payload = payload.strip()
    if not payload:
        if strict:
            raise ValueError("empty")
        return {}
    try:
        return json.loads(payload)
    except ValueError:
        if strict:
            raise
    return {}
""",
        encoding="utf-8",
    )
    (source / "response_parser.py").write_text(
        """
def _try_parse_json(payload, strict=False):
    candidate = payload.strip()
    if candidate.startswith("```json"):
        rows = candidate.splitlines()
        candidate = "\\n".join(rows[1:-1])
    candidate = candidate.strip()
    if candidate == "":
        if strict:
            raise ValueError("empty")
        return {}
    try:
        return json.loads(candidate)
    except ValueError:
        if strict:
            raise
    return {}
""",
        encoding="utf-8",
    )


def _write_parser_subdomain_split(tmp_path) -> None:
    source = tmp_path / "src" / "versions"
    source.mkdir(parents=True, exist_ok=True)
    (source / "glibc_parser.py").write_text(
        """
def parse_glibc_version(text, strict=False):
    normalized = text.strip().replace("-", ".")
    parts = []
    for item in normalized.split("."):
        if item == "":
            continue
        try:
            parts.append(int(item))
        except ValueError:
            if strict:
                raise
            parts.append(0)
    if len(parts) == 0:
        if strict:
            raise ValueError("empty")
        return ()
    if len(parts) == 1:
        parts.append(0)
    return tuple(parts)
""",
        encoding="utf-8",
    )
    (source / "local_parser.py").write_text(
        """
def parse_local_version(text, strict=False):
    normalized = text.replace("_", ".").strip()
    parts = []
    for item in normalized.split("."):
        if item == "":
            continue
        try:
            parts.append(int(item))
        except ValueError:
            if strict:
                raise
            parts.append(0)
    if len(parts) == 0:
        if strict:
            raise ValueError("empty")
        return ()
    if len(parts) == 1:
        parts.append(0)
    return tuple(parts)
""",
        encoding="utf-8",
    )


def _write_same_domain_local_parsers(tmp_path) -> None:
    source = tmp_path / "src" / "versions"
    source.mkdir(parents=True, exist_ok=True)
    (source / "local_version.py").write_text(
        """
def parse_local_version(text, strict=False):
    normalized = text.replace("_", ".").strip()
    parts = []
    for item in normalized.split("."):
        if item == "":
            continue
        try:
            parts.append(int(item))
        except ValueError:
            if strict:
                raise
            parts.append(0)
    if len(parts) == 0:
        if strict:
            raise ValueError("empty")
        return ()
    if len(parts) == 1:
        parts.append(0)
    return tuple(parts)
""",
        encoding="utf-8",
    )
    (source / "local_tag.py").write_text(
        """
def parse_local_tag(text, strict=False):
    normalized = text.strip().replace("_", ".")
    parts = []
    for item in normalized.split("."):
        if item == "":
            continue
        try:
            parts.append(int(item))
        except ValueError:
            if strict:
                raise
            parts.append(0)
    if len(parts) == 0:
        if strict:
            raise ValueError("empty")
        return ()
    if len(parts) == 1:
        parts.append(0)
    return tuple(parts)
""",
        encoding="utf-8",
    )


def _write_same_role_renderers(tmp_path) -> None:
    source = tmp_path / "src" / "maps"
    source.mkdir(parents=True, exist_ok=True)
    (source / "project_renderer.py").write_text(
        """
def render_project_map(entries, options, budget):
    lines = []
    for entry in entries:
        name = entry.get("name", "")
        details = entry.get("details", [])
        if not details:
            continue
        row = [name]
        for detail in details:
            row.append(f"- {detail}")
        if options.get("include_budget"):
            row.append(str(budget.get(name, 0)))
        lines.append("\\n".join(row))
    if options.get("footer"):
        lines.append("rendered")
    return "\\n\\n".join(lines)
""",
        encoding="utf-8",
    )
    (source / "module_renderer.py").write_text(
        """
def render_module_map(items, settings, budget):
    output = []
    for item in items:
        name = item.get("name", "")
        details = item.get("details", [])
        if details == []:
            continue
        block = [name]
        for detail in details:
            block.append(f"- {detail}")
        if settings.get("include_budget") is True:
            block.append(str(budget.get(name, 0)))
        output.append("\\n".join(block))
    if settings.get("footer") is True:
        output.append("rendered")
    return "\\n\\n".join(output)
""",
        encoding="utf-8",
    )


def _write_color_rename_mappers(tmp_path) -> None:
    source = tmp_path / "src" / "maps"
    source.mkdir(parents=True, exist_ok=True)
    (source / "visual_map.py").write_text(
        """
def _module_color_map(modules, palette, tiers):
    mapped = {}
    for module in modules:
        tier = tiers.get(module, "default")
        if tier in palette:
            mapped[module] = palette[tier]
        else:
            mapped[module] = palette.get("default", "gray")
        if module.startswith("test"):
            mapped[module] = palette.get("test", mapped[module])
    return mapped
""",
        encoding="utf-8",
    )
    (source / "rename_map.py").write_text(
        """
def module_rename_map(modules, rename_rules, moves):
    mapped = {}
    for module in modules:
        target = moves.get(module, module)
        if module in rename_rules:
            mapped[module] = rename_rules[module]
        else:
            mapped[module] = target
        if module.startswith("legacy"):
            mapped[module] = f"new.{mapped[module]}"
    return mapped
""",
        encoding="utf-8",
    )


def _write_color_mapper_pair(tmp_path) -> None:
    source = tmp_path / "src" / "maps"
    source.mkdir(parents=True, exist_ok=True)
    (source / "module_colors.py").write_text(
        """
def _module_color_map(modules, palette, tiers):
    mapped = {}
    for module in modules:
        tier = tiers.get(module, "default")
        if tier in palette:
            mapped[module] = palette[tier]
        else:
            mapped[module] = palette.get("default", "gray")
        if module.startswith("test"):
            mapped[module] = palette.get("test", mapped[module])
    return mapped
""",
        encoding="utf-8",
    )
    (source / "component_colors.py").write_text(
        """
def _component_color_map(components, palette, roles):
    mapped = {}
    for component in components:
        role = roles.get(component, "default")
        if role not in palette:
            mapped[component] = palette.get("default", "gray")
        else:
            mapped[component] = palette[role]
        if component.startswith("internal"):
            mapped[component] = palette.get("internal", mapped[component])
    return mapped
""",
        encoding="utf-8",
    )


def _write_rename_mapper_pair(tmp_path) -> None:
    source = tmp_path / "src" / "maps"
    source.mkdir(parents=True, exist_ok=True)
    (source / "module_renames.py").write_text(
        """
def module_rename_map(modules, rename_rules, moves):
    mapped = {}
    for module in modules:
        target = moves.get(module, module)
        if module in rename_rules:
            mapped[module] = rename_rules[module]
        else:
            mapped[module] = target
        if module.startswith("legacy"):
            mapped[module] = f"new.{mapped[module]}"
    return mapped
""",
        encoding="utf-8",
    )
    (source / "package_renames.py").write_text(
        """
def package_rename_map(packages, rename_rules, moves):
    mapped = {}
    for package in packages:
        target = moves.get(package, package)
        if package in rename_rules and target != package:
            mapped[package] = rename_rules[package]
        elif package in rename_rules:
            mapped[package] = rename_rules[package]
        else:
            mapped[package] = target
        if package.startswith("deprecated"):
            mapped[package] = f"new.{mapped[package]}"
    return mapped
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


def _module_text(*, import_existing: bool = False) -> str:
    reuse = "import policy_existing\n" if import_existing else ""
    reuse_call = (
        "    policy_existing.evaluate_component_policy(component, rules, context)\n"
        if import_existing
        else ""
    )
    return f"""
import json
from collections import defaultdict
from pathlib import Path
{reuse}

def load_policy_rules(path):
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    rules = []
    for item in data.get("rules", []):
        if not item.get("disabled"):
            rules.append(dict(item))
    return rules

def normalize_policy_rules(rules):
    normalized = []
    for rule in rules:
        entry = dict(rule)
        entry["component"] = entry.get("component", "*")
        entry["decision"] = entry.get("decision", "deny")
        entry["name"] = entry.get("name", entry["component"])
        normalized.append(entry)
    return normalized

def evaluate_component_policy(component, rules, context):
{reuse_call}    allowed = []
    denied = []
    for rule in normalize_policy_rules(rules):
        target = rule.get("component")
        if target not in ("*", component):
            continue
        decision = rule.get("decision")
        if decision == "allow":
            allowed.append(rule.get("name", target))
        elif decision == "deny":
            denied.append(rule.get("name", target))
    if context.get("maintenance"):
        denied.append("maintenance")
    if context.get("owner") == component:
        allowed.append("owner")
    return bool(allowed) and not denied

def explain_policy_decision(component, rules, context):
    details = []
    grouped = defaultdict(list)
    for rule in normalize_policy_rules(rules):
        grouped[rule.get("decision", "deny")].append(rule.get("name", component))
    for decision, names in sorted(grouped.items()):
        for name in names:
            details.append(f"{{decision}}:{{name}}")
    if context.get("maintenance"):
        details.append("deny:maintenance")
    return details

def summarize_policy_audit(events):
    summary = defaultdict(int)
    for event in events:
        summary[event.get("decision", "unknown")] += 1
        if event.get("component"):
            summary[event.get("component")] += 1
    return dict(summary)
"""


def _write_file_shadow_policy_modules(tmp_path, *, import_existing: bool = False) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "policy_existing.py").write_text(_module_text(), encoding="utf-8")
    (source / "policy_candidate.py").write_text(
        _module_text(import_existing=import_existing),
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


def test_shadow_implementation_suppresses_renderer_assembler_split(tmp_path) -> None:
    _write_render_assembly_split(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns == []


def test_shadow_implementation_keeps_parser_helper_pair(tmp_path) -> None:
    _write_parser_helpers(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns
    concern = concerns[0]
    assert concern["location"]["symbol"] == "_try_parse_json"
    assert concern["references"][0]["symbol"] == "parse_json_block"
    assert "shadow_implementation.role=parser" in concern["evidence"]


def test_shadow_implementation_suppresses_runtime_local_parser_subdomain_split(tmp_path) -> None:
    _write_parser_subdomain_split(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns == []


def test_shadow_implementation_keeps_same_domain_local_parser_pair(tmp_path) -> None:
    _write_same_domain_local_parsers(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns
    assert concerns[0]["kind"] == "shadow-implementation"
    assert "shadow_implementation.role=parser" in concerns[0]["evidence"]


def test_shadow_implementation_keeps_same_role_renderer_pair(tmp_path) -> None:
    _write_same_role_renderers(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns
    assert concerns[0]["kind"] == "shadow-implementation"
    assert "shadow_implementation.role=mapper" in concerns[0]["evidence"]


def test_shadow_implementation_suppresses_color_mapper_rename_mapper_split(tmp_path) -> None:
    _write_color_rename_mappers(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns == []


def test_shadow_implementation_keeps_same_domain_color_mapper_pair(tmp_path) -> None:
    _write_color_mapper_pair(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns
    assert concerns[0]["kind"] == "shadow-implementation"
    assert "shadow_implementation.role=mapper" in concerns[0]["evidence"]


def test_shadow_implementation_keeps_same_domain_rename_mapper_pair(tmp_path) -> None:
    _write_rename_mapper_pair(tmp_path)

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns
    assert concerns[0]["kind"] == "shadow-implementation"
    assert "shadow_implementation.role=mapper" in concerns[0]["evidence"]


def test_shadow_implementation_scoped_suppresses_changed_renderer_assembler_split(tmp_path) -> None:
    _write_render_assembly_split(tmp_path)

    concerns = shadow_implementation_concerns(
        tmp_path,
        changed_files=["src/maps/assembler.py"],
    )

    assert concerns == []


def test_shadow_implementation_scoped_suppresses_changed_color_rename_mapper_split(tmp_path) -> None:
    _write_color_rename_mappers(tmp_path)

    concerns = shadow_implementation_concerns(
        tmp_path,
        changed_files=["src/maps/rename_map.py"],
    )

    assert concerns == []


def test_shadow_implementation_scoped_suppresses_changed_parser_subdomain_split(tmp_path) -> None:
    _write_parser_subdomain_split(tmp_path)

    concerns = shadow_implementation_concerns(
        tmp_path,
        changed_files=["src/versions/local_parser.py"],
    )

    assert concerns == []


def test_shadow_implementation_file_dry_run_reports_policy_module_pair(tmp_path) -> None:
    _write_file_shadow_policy_modules(tmp_path)

    result = shadow_implementation_file_dry_run(tmp_path)

    assert result["mode"] == "dry_run"
    assert result["candidate_total"] == 2
    assert result["pair_total"] == 1
    candidate = result["candidates"][0]
    assert candidate["left"]["path"] == "src/policy_candidate.py"
    assert candidate["right"]["path"] == "src/policy_existing.py"
    assert candidate["role"] == "policy"
    assert candidate["metrics"]["public_api_overlap"] >= 0.55
    assert candidate["metrics"]["symbol_shape_similarity"] >= 0.65
    assert candidate["metrics"]["ast_similarity"] >= 0.88
    assert candidate["metrics"]["import_similarity"] >= 0.45
    assert "shadow_implementation.file.reuse_edge=false" in candidate["facts"]


def test_shadow_implementation_file_dry_run_ignores_reusing_module(tmp_path) -> None:
    _write_file_shadow_policy_modules(tmp_path, import_existing=True)

    result = shadow_implementation_file_dry_run(tmp_path)

    assert result["candidate_total"] == 2
    assert result["pair_total"] == 0
    assert result["candidates"] == []


def test_shadow_implementation_file_dry_run_excludes_report_view_split_modules(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "report_views.py").write_text(_module_text().replace("policy", "report"), encoding="utf-8")
    (source / "report_sections.py").write_text(_module_text().replace("policy", "report"), encoding="utf-8")

    result = shadow_implementation_file_dry_run(tmp_path)

    assert result["candidate_total"] == 0
    assert result["pair_total"] == 0
    assert result["by_exclusion"]["split_module_name"] == 2


def test_shadow_implementation_file_dry_run_ignores_small_modules(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "policy_a.py").write_text("def load_policy_rules(path):\n    return []\n", encoding="utf-8")
    (source / "policy_b.py").write_text("def load_policy_rules(path):\n    return []\n", encoding="utf-8")

    result = shadow_implementation_file_dry_run(tmp_path)

    assert result["candidate_total"] == 0
    assert result["pair_total"] == 0
    assert result["by_exclusion"]["too_small"] == 2


def test_shadow_implementation_file_dry_run_ignores_ccb_state_modules(tmp_path) -> None:
    source = tmp_path / ".ccb" / "agents" / "agent1" / "provider-state"
    source.mkdir(parents=True)
    (source / "policy_existing.py").write_text(_module_text(), encoding="utf-8")
    (source / "policy_candidate.py").write_text(_module_text(), encoding="utf-8")

    result = shadow_implementation_file_dry_run(tmp_path)

    assert result["candidate_total"] == 0
    assert result["pair_total"] == 0
    assert result["reported_total"] == 0
    assert result["candidates"] == []


def test_shadow_implementation_concerns_ignore_benchmark_dirs_but_keep_src_candidates(tmp_path) -> None:
    _write_shadow_policy_project_with_paths(
        tmp_path,
        existing_path="benchmarks/base_policy.py",
        candidate_path="benchmarks/generated_policy.py",
    )
    _write_shadow_policy_project_with_paths(
        tmp_path,
        existing_path="src/policy/base_policy.py",
        candidate_path="src/policy/generated_policy.py",
    )

    concerns = shadow_implementation_concerns(tmp_path)

    assert concerns
    assert all("benchmarks/" not in concern["location"]["path"] for concern in concerns)
    assert all("benchmarks/" not in concern["references"][0]["path"] for concern in concerns)
    assert concerns[0]["location"]["path"].startswith("src/policy/")


def test_shadow_implementation_file_dry_run_ignores_benchmark_dirs(tmp_path) -> None:
    source = tmp_path / "benchmarks"
    source.mkdir()
    (source / "policy_existing.py").write_text(_module_text(), encoding="utf-8")
    (source / "policy_candidate.py").write_text(_module_text(), encoding="utf-8")

    result = shadow_implementation_file_dry_run(tmp_path)

    assert result["candidate_total"] == 0
    assert result["pair_total"] == 0
    assert result["reported_total"] == 0
    assert result["candidates"] == []


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


def test_shadow_implementation_concerns_ignore_ccb_state_functions_and_classes(tmp_path) -> None:
    _write_shadow_policy_project_with_paths(
        tmp_path,
        existing_path=".ccb/agents/agent1/provider-state/base_policy.py",
        candidate_path=".ccb/agents/agent1/provider-state/generated_policy.py",
    )
    state_dir = tmp_path / ".ccb" / "agents" / "agent1" / "provider-state"
    (state_dir / "base_class.py").write_text(
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
    (state_dir / "candidate_class.py").write_text(
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

    assert shadow_implementation_concerns(tmp_path) == []


def test_shadow_implementation_concern_id_is_stable(tmp_path) -> None:
    _write_shadow_policy_project(tmp_path)

    first = shadow_implementation_concerns(tmp_path)
    second = shadow_implementation_concerns(tmp_path)

    assert [item["concern_id"] for item in first] == [item["concern_id"] for item in second]


def test_shadow_implementation_scoped_changed_file_is_primary_location(tmp_path) -> None:
    _write_shadow_policy_project_with_paths(
        tmp_path,
        existing_path="src/policy/z_existing_policy.py",
        candidate_path="src/policy/a_candidate_policy.py",
    )

    concerns = shadow_implementation_concerns(
        tmp_path,
        changed_files=["src/policy/a_candidate_policy.py"],
    )

    assert concerns
    assert concerns[0]["location"]["path"] == "src/policy/a_candidate_policy.py"
    assert concerns[0]["references"][0]["path"] == "src/policy/z_existing_policy.py"


def test_shadow_implementation_scoped_without_changed_candidate_is_empty(tmp_path) -> None:
    _write_shadow_policy_project(tmp_path)

    assert shadow_implementation_concerns(tmp_path, changed_files=["src/unrelated.py"]) == []


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


def test_code_review_outputs_do_not_include_file_level_shadow_dry_run(tmp_path, monkeypatch) -> None:
    _write_shadow_policy_project(tmp_path)
    _write_shadow_policy_classes(tmp_path)
    report = {
        **_empty_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/policy/generated_policy.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    full_result = code_review.run_code_review_full(tmp_path)
    diff_result = code_review.run_code_review_diff(tmp_path)
    since_result = code_review.run_code_review_since(tmp_path, ref="main")

    for result in (full_result, diff_result, since_result):
        shadow_concerns = [item for item in result["concerns"] if item["kind"] == "shadow-implementation"]
        assert shadow_concerns
        assert all(item["location"]["symbol_kind"] != "module" for item in shadow_concerns)
        payload = json.dumps(result, sort_keys=True)
        assert "shadow_implementation.file." not in payload


def test_code_review_diff_includes_changed_file_scoped_shadow_signal(tmp_path, monkeypatch) -> None:
    _write_shadow_policy_project(tmp_path)
    report = {
        **_empty_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/policy/generated_policy.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    concern = next(item for item in result["concerns"] if item["kind"] == "shadow-implementation")
    assert concern["location"]["path"] == "src/policy/generated_policy.py"
    assert concern["references"][0]["path"] == "src/policy/base_policy.py"
    signal = next(item for item in result["signals"] if item["kind"] == "shadow_implementation")
    assert signal["metrics"]["scoped_to_changed_files"] is True
    assert signal["metrics"]["changed_file_total"] == 1
    assert signal["metrics"]["candidate_total_before_scope"] >= signal["metrics"]["candidate_total"]


def test_code_review_since_includes_changed_file_scoped_shadow_signal(tmp_path, monkeypatch) -> None:
    _write_shadow_policy_classes(tmp_path)
    report = {
        **_empty_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/policy/candidate_class.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_since(tmp_path, ref="main")

    concern = next(
        item
        for item in result["concerns"]
        if item["kind"] == "shadow-implementation" and item["location"]["symbol_kind"] == "class"
    )
    assert concern["location"]["path"] == "src/policy/candidate_class.py"
    assert concern["references"][0]["path"] == "src/policy/base_class.py"
    signal = next(item for item in result["signals"] if item["kind"] == "shadow_implementation")
    assert signal["metrics"]["scoped_to_changed_files"] is True
    assert signal["metrics"]["by_symbol_kind"]["class"] == 1


def test_code_review_since_bad_ref_does_not_run_shadow_detector(tmp_path, monkeypatch) -> None:
    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    def fail_shadow(*args, **kwargs):
        raise AssertionError("shadow detector should not run")

    monkeypatch.setattr(code_review, "run_analysis", raise_bad_ref)
    monkeypatch.setattr(code_review, "shadow_implementation_scan", fail_shadow)

    result = code_review.run_code_review_since(tmp_path, ref="missing")

    assert result["review_type"] == "since"
    assert result["concerns"] == []
    assert result["signals"] == []


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
