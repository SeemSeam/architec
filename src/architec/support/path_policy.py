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
    ".el",
    ".elm",
    ".dart",
    ".scala",
    ".sc",
    ".ex",
    ".exs",
    ".jl",
    ".ml",
    ".mli",
    ".zig",
    ".f",
    ".f90",
    ".f95",
    ".f03",
    ".for",
    ".m",
    ".tf",
    ".hcl",
}
_EXCLUDED_SEGMENTS = {
    ".git",
    ".hippos",
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
_DOC_NAMES = {
    "readme",
    "changelog",
    "changes",
    "license",
    "licence",
    "authors",
    "contributors",
    "copying",
    "notice",
}
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
_KNOWN_EXTENSIONLESS_SOURCE_NAMES = {
    "makefile",
    "dockerfile",
    "justfile",
    "jenkinsfile",
    "rakefile",
    "gemfile",
    "vagrantfile",
    "brewfile",
}
_TEXT_PROBE_BYTES = 4096
_SHEBANG_SOURCE_NAMES = {
    "python",
    "python2",
    "python3",
    "python3.11",
    "node",
    "nodejs",
    "deno",
    "bun",
    "ruby",
    "php",
    "sh",
    "bash",
    "zsh",
    "fish",
    "ksh",
    "dash",
    "ash",
    "perl",
}


def _normalize_segment(segment: str) -> str:
    raw = str(segment or "").strip().lower()
    return "".join(ch for ch in raw if ch.isalnum())


def _is_packaging_metadata_segment(segment: str) -> bool:
    name = str(segment or "").strip().lower()
    return name.endswith(".egg-info") or name.endswith(".dist-info")


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
    name = parts[-1]
    stem = _normalize_segment(Path(name).stem or Path(name).name)
    if any(stem.startswith(token) for token in _DOC_NAMES):
        return True
    suffix = Path(name).suffix.lower()
    return suffix in {".md", ".rst", ".txt", ".adoc"}


def is_generated_like_path(path: str) -> bool:
    name = Path(normalize_relpath(path)).name.lower()
    if name.endswith((".min.js", ".bundle.js", ".pb.go")):
        return True
    return any(token in name for token in (".generated.", ".gen.", "_generated.", "_pb2.py", "_pb2_grpc.py"))


def _candidate_interpreters(line: str) -> list[str]:
    body = line[2:].strip()
    if not body:
        return []
    tokens = [token for token in body.split() if token]
    if not tokens:
        return []
    first = Path(tokens[0]).name.lower()
    if first != "env":
        return [first]
    out: list[str] = []
    for token in tokens[1:]:
        lowered = Path(token).name.lower()
        if lowered.startswith("-"):
            continue
        out.append(lowered)
    return out


def _looks_like_code_text(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()][:40]
    if not lines:
        return False
    if any(line.startswith("<?php") for line in lines[:8]):
        return True
    py_score = 0
    js_score = 0
    ruby_score = 0
    for line in lines:
        if line.startswith(("import ", "from ", "def ", "class ", "async def ")):
            py_score += 2
        if line.startswith(("@", "return ", "raise ", "yield ")):
            py_score += 1
        if line.startswith(("if ", "elif ", "else:", "for ", "while ", "with ", "try:", "except ", "finally:", "match ", "case ")):
            py_score += 1
        if "__main__" in line:
            py_score += 3

        if line.startswith(("import ", "export ", "const ", "let ", "var ", "function ")):
            js_score += 2
        if "=>" in line or "require(" in line or "module.exports" in line:
            js_score += 1

        if line.startswith(("require ", "def ", "class ", "module ")):
            ruby_score += 2
        if line in {"end", "begin"} or line.startswith("attr_"):
            ruby_score += 1
    return py_score >= 3 or js_score >= 3 or ruby_score >= 3


def _probe_extensionless_kind(path: Path) -> str:
    name = path.name.lower()
    stem = _normalize_segment(Path(name).stem or Path(name).name)
    if any(stem.startswith(token) for token in _DOC_NAMES):
        return "doc"
    if name in _KNOWN_EXTENSIONLESS_SOURCE_NAMES:
        return "source"
    try:
        with path.open("rb") as handle:
            data = handle.read(_TEXT_PROBE_BYTES)
    except OSError:
        return "unsupported"
    if not data or b"\0" in data:
        return "unsupported"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "unsupported"
    if text.startswith("#!"):
        first_line = text.splitlines()[0] if text.splitlines() else text
        if any(candidate.startswith("python") or candidate in _SHEBANG_SOURCE_NAMES for candidate in _candidate_interpreters(first_line)):
            return "source"
    return "source" if _looks_like_code_text(text) else "unsupported"


def _resolve_probe_path(path: str | Path, probe_root: Path | None) -> Path | None:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    if probe_root is None:
        return None
    return probe_root / normalize_relpath(str(path))


def path_kind(path: str | Path, *, probe_root: Path | None = None) -> str:
    parts = _parts(str(path))
    if not parts:
        return "unknown"
    normalized = [_normalize_segment(seg) for seg in parts]
    if any(seg.startswith(".") for seg in parts):
        return "hidden"
    if any(_is_packaging_metadata_segment(seg) for seg in parts):
        return "excluded"
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
    if suffix:
        return "source"
    name = parts[-1].lower()
    if name in _KNOWN_EXTENSIONLESS_SOURCE_NAMES:
        return "source"
    probe_path = _resolve_probe_path(path, probe_root)
    if probe_path is None or not probe_path.is_file():
        return "unsupported"
    return _probe_extensionless_kind(probe_path)


def is_relevant_arch_path(path: str | Path, *, probe_root: Path | None = None) -> bool:
    return path_kind(path, probe_root=probe_root) == "source"
