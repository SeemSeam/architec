from __future__ import annotations

from pathlib import Path

from .io_utils import normalize_relpath

_CODE_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".kts",
    ".swift",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".hxx",
    ".cs",
    ".rb",
    ".php",
    ".dart",
    ".scala",
    ".sc",
    ".ex",
    ".exs",
    ".jl",
    ".ml",
    ".mli",
    ".zig",
    ".tf",
    ".hcl",
}
_EXCLUDED_SEGMENTS = {
    ".git",
    ".hippocampus",
    ".architec",
    ".ccb",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "target",
    "out",
    "bin",
    "obj",
    "vendor",
    "third_party",
    "third-party",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".parcel-cache",
    ".cache",
    "coverage",
    "htmlcov",
    "tmp",
    "temp",
    "site-packages",
    "release-flow-test",
    "local-test-env",
}
_DOC_SEGMENTS = {"docs", "doc", "documentation", "plans"}
_FIXTURE_SEGMENTS = {"fixtures", "fixture", "mocks", "mock", "testdata"}
_INFRA_SEGMENTS = {"infra", "terraform", "helm", "charts", "k8s", "deploy", "deployment"}
_TEST_SEGMENTS = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
    "unittest",
    "unittests",
    "integrationtest",
    "integrationtests",
    "e2e",
    "e2etests",
    "benches",
    "benchmark",
    "benchmarks",
}


def _normalize_segment(segment: str) -> str:
    raw = str(segment or "").strip().lower()
    return "".join(ch for ch in raw if ch.isalnum())


def _parts(path: str) -> list[str]:
    return [seg for seg in normalize_relpath(path).split("/") if seg]


def is_test_like_path(path: str) -> bool:
    parts = _parts(path)
    if not parts:
        return False
    normalized = [_normalize_segment(seg) for seg in parts]
    if any(
        seg in _TEST_SEGMENTS or seg.endswith("tests") or seg.endswith("specs")
        for seg in normalized[:-1]
    ):
        return True
    name = parts[-1].lower()
    if name.startswith(("test_", "spec_")):
        return True
    if name.endswith(("_test.py", "_test.go", "_test.rb", "_test.dart", "_spec.py", "_spec.rb")):
        return True
    if ".test." in name or ".spec." in name:
        return True
    if name.endswith("test.php"):
        return True
    return False


def is_doc_like_path(path: str) -> bool:
    parts = _parts(path)
    if not parts:
        return False
    if any(_normalize_segment(seg) in _DOC_SEGMENTS for seg in parts[:-1]):
        return True
    suffix = Path(parts[-1]).suffix.lower()
    return suffix in {".md", ".rst", ".txt", ".adoc"}


def is_generated_like_path(path: str) -> bool:
    name = Path(normalize_relpath(path)).name.lower()
    if name.endswith((".min.js", ".bundle.js", ".pb.go")):
        return True
    return any(token in name for token in (".generated.", ".gen.", "_generated.", "_pb2.py", "_pb2_grpc.py"))


def path_kind(path: str) -> str:
    parts = _parts(path)
    if not parts:
        return "unknown"
    normalized = [_normalize_segment(seg) for seg in parts]
    if any(seg.startswith(".") for seg in parts):
        return "hidden"
    if any(seg in _EXCLUDED_SEGMENTS or norm in _EXCLUDED_SEGMENTS for seg, norm in zip(parts[:-1], normalized[:-1])):
        return "excluded"
    if is_doc_like_path(path):
        return "doc"
    if any(norm in _FIXTURE_SEGMENTS for norm in normalized[:-1]):
        return "fixture"
    if any(norm in _INFRA_SEGMENTS for norm in normalized[:-1]) or Path(parts[-1]).suffix.lower() in {".tf", ".hcl"}:
        return "infra"
    if is_generated_like_path(path):
        return "generated"
    if is_test_like_path(path):
        return "test"
    suffix = Path(parts[-1]).suffix.lower()
    if suffix and suffix not in _CODE_SUFFIXES:
        return "unsupported"
    return "source"


def is_relevant_arch_path(path: str) -> bool:
    return path_kind(path) == "source"
