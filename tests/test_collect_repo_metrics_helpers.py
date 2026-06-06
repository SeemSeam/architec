from __future__ import annotations

import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from collect_repo_metrics_python import analyze_python_file
from collect_repo_metrics import collect_metrics
from collect_repo_metrics_rules import load_architecture_rules
from collect_repo_metrics_scan import iter_files, line_length_summary, module_size_findings
from architec.integration.bundle_loader import compute_bundle_fingerprint


class _Thr:
    cc_soft = 8
    cc_hard = 12
    class_methods_soft = 2
    class_attrs_soft = 1
    line_soft = 10
    line_hard = 20
    module_soft = 3
    module_hard = 5


def test_analyze_python_file_reports_complexity() -> None:
    text = """
def f(x):
    if x:
        for i in range(3):
            if i % 2:
                pass
    elif x == 0:
        while x < 10:
            x += 1
    else:
        try:
            assert x
        except AssertionError:
            x = 1
        finally:
            x += 1
    return x
"""
    result = analyze_python_file(rel="a.py", text=text, thr=_Thr())
    assert result["function_count"] == 1
    assert any(item["metric"] == "cyclomatic_complexity" for item in result["findings"])


def test_module_size_and_line_length_helpers() -> None:
    thr = _Thr()
    size_findings = module_size_findings(rel="a.py", line_count=6, thr=thr)
    line_summary = line_length_summary(rel="a.py", lines=["x" * 25], thr=thr)
    assert size_findings[0]["metric"] == "module_lines"
    assert line_summary["hard_hits"] == 1
    assert line_summary["findings"][0]["metric"] == "line_length_hard_hits"


def test_iter_files_skips_generated_state_dirs(tmp_path: Path) -> None:
    included = tmp_path / "src" / "keep.py"
    generated = tmp_path / ".architec" / "generated.json"
    hippos_bundle = tmp_path / ".hippos" / "architect-metrics.json"
    bundled = tmp_path / ".hippocampus" / "architect-metrics.json"
    included.parent.mkdir(parents=True, exist_ok=True)
    generated.parent.mkdir(parents=True, exist_ok=True)
    hippos_bundle.parent.mkdir(parents=True, exist_ok=True)
    bundled.parent.mkdir(parents=True, exist_ok=True)
    included.write_text("print('ok')\n", encoding="utf-8")
    generated.write_text("{}\n", encoding="utf-8")
    hippos_bundle.write_text("{}\n", encoding="utf-8")
    bundled.write_text("{}\n", encoding="utf-8")

    files = iter_files(tmp_path, exclude_dirs=set(), exclude_suffixes=set())

    assert included in files
    assert generated not in files
    assert hippos_bundle not in files
    assert bundled not in files


def test_collect_metrics_includes_canonical_hippos_bundle_fingerprint(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    hippos = root / ".hippos"
    hippos.mkdir(parents=True, exist_ok=True)
    (hippos / "hippos-index.json").write_text('{"files":{"src/app.py":{}}}\n', encoding="utf-8")
    (hippos / "code-signatures.json").write_text(
        '{"files":{"src/app.py":{"signatures":[]}}}\n',
        encoding="utf-8",
    )
    (hippos / "file-manifest.json").write_text(
        json.dumps({"files": {"src/app.py": {"kind": "source"}}}) + "\n",
        encoding="utf-8",
    )

    result = collect_metrics(root, {"exclude_dirs": [], "exclude_suffixes": [], "weights": {}})

    assert result["bundle_fingerprint"]
    assert result["bundle_fingerprint"] == compute_bundle_fingerprint(root)


def test_collect_metrics_includes_bundle_fingerprint(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    hippo = root / ".hippocampus"
    hippo.mkdir(parents=True, exist_ok=True)
    (hippo / "hippocampus-index.json").write_text('{"files":{"src/app.py":{}}}\n', encoding="utf-8")
    (hippo / "code-signatures.json").write_text(
        '{"files":{"src/app.py":{"signatures":[]}}}\n',
        encoding="utf-8",
    )
    (hippo / "file-manifest.json").write_text(
        json.dumps({"files": {"src/app.py": {"kind": "source"}}}) + "\n",
        encoding="utf-8",
    )

    result = collect_metrics(root, {"exclude_dirs": [], "exclude_suffixes": [], "weights": {}})

    assert result["bundle_fingerprint"]
    assert result["bundle_fingerprint"] == compute_bundle_fingerprint(root)


def test_iter_files_applies_shared_and_archi_rule_file(tmp_path: Path) -> None:
    included = tmp_path / "src" / "keep.py"
    ignored_by_shared = tmp_path / "tmp" / "skip.py"
    ignored_by_archi = tmp_path / "src" / "legacy" / "old.py"
    ignored_by_glob = tmp_path / "notes.skip"
    included.parent.mkdir(parents=True, exist_ok=True)
    ignored_by_shared.parent.mkdir(parents=True, exist_ok=True)
    ignored_by_archi.parent.mkdir(parents=True, exist_ok=True)
    included.write_text("print('ok')\n", encoding="utf-8")
    ignored_by_shared.write_text("print('skip')\n", encoding="utf-8")
    ignored_by_archi.write_text("print('old')\n", encoding="utf-8")
    ignored_by_glob.write_text("skip\n", encoding="utf-8")
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[shared]",
                'ignore_paths = ["tmp"]',
                "",
                "[archi]",
                'ignore_paths = ["src/legacy"]',
                'ignore_extensions = [".skip"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    files = iter_files(
        tmp_path,
        exclude_dirs=set(),
        exclude_suffixes=set(),
        rules=load_architecture_rules(tmp_path),
    )

    assert included in files
    assert ignored_by_shared not in files
    assert ignored_by_archi not in files
    assert ignored_by_glob not in files
