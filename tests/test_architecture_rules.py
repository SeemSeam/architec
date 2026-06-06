from __future__ import annotations

from architec.support.architecture_rules import (
    cleanup_metadata_for_candidate,
    load_archi_rules,
    load_architecture_rules,
)


def test_load_archi_rules_merges_cleanup_metadata_rules_and_resolves_candidate_metadata(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[shared.cleanup_metadata]]",
                'glob = "docs/legacy/**"',
                'owner = "docs-platform"',
                "ttl_days = 30",
                "",
                "[[archi.cleanup_metadata]]",
                'path = "docs/legacy/guide.md"',
                'expires_at = "2099-01-01"',
                'category = "stale_doc"',
                "",
                "[[archi.cleanup_metadata]]",
                'path = "docs/legacy/expired.md"',
                'expires_at = "2000-01-01"',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rules = load_archi_rules(tmp_path)

    future_metadata = cleanup_metadata_for_candidate(
        "docs/legacy/guide.md",
        rules=rules,
        kind="doc",
        category="stale_doc",
    )
    expired_metadata = cleanup_metadata_for_candidate(
        "docs/legacy/expired.md",
        rules=rules,
        kind="doc",
        category="stale_doc",
    )

    assert future_metadata == {
        "owner": "docs-platform",
        "ttl_days": 30,
        "expires_at": "2099-01-01",
        "expired": False,
    }
    assert expired_metadata["owner"] == "docs-platform"
    assert expired_metadata["ttl_days"] == 30
    assert expired_metadata["expires_at"] == "2000-01-01"
    assert expired_metadata["expired"] is True


def test_load_archi_rules_reads_architecture_contract_rules(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[shared.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/api/**"',
                'owner = "api"',
                'restricted_imports = ["app.storage", "app.storage.*"]',
                'note = "Use the service facade."',
                "",
                "[[archi.architecture_contracts]]",
                'id = "domain-no-cli"',
                'source_glob = "src/domain/**"',
                'forbidden_imports = ["app.cli"]',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rules = load_archi_rules(tmp_path)

    assert [rule.rule_id for rule in rules.architecture_contract_rules] == [
        "api-no-storage",
        "domain-no-cli",
    ]
    api_rule = rules.architecture_contract_rules[0]
    assert api_rule.source_glob == "src/api/**"
    assert api_rule.owner == "api"
    assert api_rule.restricted_imports == ("app.storage", "app.storage.*")
    assert api_rule.note == "Use the service facade."


def test_load_hippos_rules_merges_legacy_hippo_section(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[hippo]",
                'ignore_paths = ["legacy-generated"]',
                "",
                "[hippos]",
                'ignore_paths = ["current-generated"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rules = load_architecture_rules(tmp_path, tool_name="hippos")

    assert rules.ignore_paths == ("legacy-generated", "current-generated")
