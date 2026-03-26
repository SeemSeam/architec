from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from collect_repo_metrics_python import analyze_python_file
from collect_repo_metrics_scan import iter_files, line_length_summary, module_size_findings


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
    bundled = tmp_path / ".hippocampus" / "architect-metrics.json"
    included.parent.mkdir(parents=True, exist_ok=True)
    generated.parent.mkdir(parents=True, exist_ok=True)
    bundled.parent.mkdir(parents=True, exist_ok=True)
    included.write_text("print('ok')\n", encoding="utf-8")
    generated.write_text("{}\n", encoding="utf-8")
    bundled.write_text("{}\n", encoding="utf-8")

    files = iter_files(tmp_path, exclude_dirs=set(), exclude_suffixes=set())

    assert included in files
    assert generated not in files
    assert bundled not in files
