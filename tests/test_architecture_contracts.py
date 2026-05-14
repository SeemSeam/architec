from __future__ import annotations

from architec.code_review.architecture_contracts import architecture_contract_scan


def test_architecture_contract_scan_reports_changed_file_restricted_import(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/api/**"',
                'owner = "api-platform"',
                'restricted_imports = ["app.storage"]',
                'note = "Use the service facade."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text(
        "from app.storage import repository\n\n\ndef handle():\n    return repository.load()\n",
        encoding="utf-8",
    )

    result = architecture_contract_scan(
        tmp_path,
        changed_files=["src/api/handler.py"],
    )

    assert result["rule_total"] == 1
    assert result["checked_file_total"] == 1
    assert result["concern_total_before_limit"] == 1
    concern = result["concerns"][0]
    assert concern["kind"] == "architecture-contract"
    assert concern["location"] == {
        "path": "src/api/handler.py",
        "line": 1,
        "symbol": "",
        "symbol_kind": "module",
    }
    assert concern["blast_radius"] == ["src/api/handler.py"]
    assert "architecture_contract.rule_id=api-no-storage" in concern["evidence"]
    assert "architecture_contract.import=app.storage" in concern["evidence"]
    assert "architecture_contract.restricted_import=app.storage" in concern["evidence"]
    assert "architecture_contract.owner=api-platform" in concern["evidence"]
    assert concern["next_steps_hint"] == "Use the service facade."


def test_architecture_contract_scan_handles_relative_imports(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/app/api/**"',
                'restricted_imports = ["app.storage"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "app" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text(
        "from ..storage import repository\n\n\ndef handle():\n    return repository.load()\n",
        encoding="utf-8",
    )

    result = architecture_contract_scan(
        tmp_path,
        changed_files=["src/app/api/handler.py"],
    )

    assert result["concerns"][0]["location"]["path"] == "src/app/api/handler.py"
    assert "architecture_contract.import=app.storage" in result["concerns"][0]["evidence"]


def test_architecture_contract_scan_handles_absolute_from_import_child(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/api/**"',
                'restricted_imports = ["app.storage"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text(
        "from app import storage\n\n\ndef handle():\n    return storage.load()\n",
        encoding="utf-8",
    )

    result = architecture_contract_scan(
        tmp_path,
        changed_files=["src/api/handler.py"],
    )

    assert result["concerns"][0]["location"]["path"] == "src/api/handler.py"
    assert "architecture_contract.import=app.storage" in result["concerns"][0]["evidence"]


def test_architecture_contract_scan_handles_relative_from_import_child(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/app/api/**"',
                'restricted_imports = ["app.storage"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "app" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text(
        "from .. import storage\n\n\ndef handle():\n    return storage.load()\n",
        encoding="utf-8",
    )

    result = architecture_contract_scan(
        tmp_path,
        changed_files=["src/app/api/handler.py"],
    )

    assert result["concerns"][0]["location"]["path"] == "src/app/api/handler.py"
    assert "architecture_contract.import=app.storage" in result["concerns"][0]["evidence"]


def test_architecture_contract_scan_stays_empty_without_contract_config(tmp_path) -> None:
    source_dir = tmp_path / "src" / "api"
    source_dir.mkdir(parents=True)
    (source_dir / "handler.py").write_text("import app.storage\n", encoding="utf-8")

    result = architecture_contract_scan(
        tmp_path,
        changed_files=["src/api/handler.py"],
    )

    assert result == {
        "concerns": [],
        "rule_total": 0,
        "checked_file_total": 0,
        "scoped_to_changed_files": True,
    }


def test_architecture_contract_scan_ignores_unchanged_files(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/api/**"',
                'restricted_imports = ["app.storage"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("import app.storage\n", encoding="utf-8")

    result = architecture_contract_scan(
        tmp_path,
        changed_files=["src/other/file.py"],
    )

    assert result["rule_total"] == 1
    assert result["checked_file_total"] == 0
    assert result["concerns"] == []


def test_architecture_contract_concern_id_is_stable(tmp_path) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/api/**"',
                'restricted_imports = ["app.storage"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("import app.storage\n", encoding="utf-8")

    first = architecture_contract_scan(tmp_path, changed_files=["src/api/handler.py"])
    second = architecture_contract_scan(tmp_path, changed_files=["./src/api/handler.py"])

    assert first["concerns"][0]["concern_id"] == second["concerns"][0]["concern_id"]
