from __future__ import annotations

import json

from architec.plan_review.public import run_plan_review


def test_recommended_template_parses_intent_changes_and_dependencies(tmp_path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## Intent
Add near-duplicate signal review for AI-generated code.

## Changes
```yaml
changes:
  - action: create
    path: src/architec/analysis/signals.py
    intent: detect near-duplicate functions
  - action: modify
    path: src/architec/reporting/report_markdown.py
    intent: include signal summary in review output
dependencies:
  - PyYAML
```

## Notes
Do not change cleanup archive behavior.
""",
        encoding="utf-8",
    )

    result = run_plan_review(plan, project_root=tmp_path)

    assert result["mode"] == "plan_review"
    understood = result["understood_plan"]
    assert understood["intent"] == "Add near-duplicate signal review for AI-generated code."
    assert understood["changes"] == [
        {
            "action": "create",
            "path": "src/architec/analysis/signals.py",
            "intent": "detect near-duplicate functions",
        },
        {
            "action": "modify",
            "path": "src/architec/reporting/report_markdown.py",
            "intent": "include signal summary in review output",
        },
    ]
    assert understood["dependencies"] == ["PyYAML"]
    assert result["concerns"] == []
    assert result["suggested_adjustments"] == []
    assert len(result["plan_fingerprint"]) == 64


def test_plan_review_missing_changes_uses_missing_context_concern(tmp_path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## Intent
Describe a narrow parser improvement.

## Notes
Keep the first step small.
""",
        encoding="utf-8",
    )

    result = run_plan_review(plan, project_root=tmp_path)

    assert result["understood_plan"]["intent"] == "Describe a narrow parser improvement."
    assert result["understood_plan"]["changes"] == []
    assert result["understood_plan"]["dependencies"] == []
    assert [concern["kind"] for concern in result["concerns"]] == ["missing-context"]
    concern = result["concerns"][0]
    assert all(not item.startswith("Add ") for item in concern["evidence"])
    assert concern["next_steps_hint"] == "Add changes entries with action, path, and intent."


def test_plan_review_bad_fenced_yaml_degrades_to_missing_context(tmp_path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## Intent
Try a parser change.

## Changes
```yaml
changes:
  - action: create
    path: [broken
dependencies: []
```
""",
        encoding="utf-8",
    )

    result = run_plan_review(plan, project_root=tmp_path)

    assert result["understood_plan"]["intent"] == "Try a parser change."
    assert result["understood_plan"]["changes"] == []
    assert result["understood_plan"]["dependencies"] == []
    assert [concern["kind"] for concern in result["concerns"]] == ["missing-context"]


def test_plan_review_non_dict_fenced_yaml_degrades_to_missing_context(tmp_path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## Intent
Try a parser change.

## Changes
```yaml
- action: create
- path: src/architec/plan_review/public.py
```
""",
        encoding="utf-8",
    )

    result = run_plan_review(plan, project_root=tmp_path)

    assert result["understood_plan"]["changes"] == []
    assert result["understood_plan"]["dependencies"] == []
    assert [concern["kind"] for concern in result["concerns"]] == ["missing-context"]


def test_plan_review_wraps_non_list_dependencies(tmp_path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## Intent
Add a local advisory parser.

## Changes
```yaml
changes:
  - action: create
    path: src/architec/plan_review/public.py
    intent: parse plan markdown
dependencies: PyYAML
```
""",
        encoding="utf-8",
    )

    result = run_plan_review(plan, project_root=tmp_path)

    assert result["understood_plan"]["changes"] == [
        {
            "action": "create",
            "path": "src/architec/plan_review/public.py",
            "intent": "parse plan markdown",
        }
    ]
    assert result["understood_plan"]["dependencies"] == ["PyYAML"]
    assert result["concerns"] == []


def test_plan_review_json_avoids_gate_terms(tmp_path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## Intent
Add a local advisory parser.

## Changes
```yaml
changes:
  - action: create
    path: src/architec/plan_review/public.py
    intent: parse plan markdown
dependencies: []
```
""",
        encoding="utf-8",
    )

    payload = json.dumps(run_plan_review(plan, project_root=tmp_path), sort_keys=True).lower()

    assert "pass" not in payload
    assert "fail" not in payload
    assert "block" not in payload
    assert "must-fix" not in payload
