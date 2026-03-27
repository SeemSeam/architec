from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..integration.hippo_adapter import HippoSnapshot
from ..support.path_policy import is_test_like_path

_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")
_PYTHON_SUFFIXES = {".py"}
_NODE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_GO_SUFFIXES = {".go"}
_RUST_SUFFIXES = {".rs"}
_JVM_SUFFIXES = {".java", ".kt", ".kts"}
_NATIVE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".f", ".f90", ".f95", ".f03", ".for"}
_DOTNET_SUFFIXES = {".cs"}
_RUBY_SUFFIXES = {".rb"}
_PHP_SUFFIXES = {".php"}
_DART_SUFFIXES = {".dart"}
_TEST_DIR_MARKERS = {"test", "tests", "__tests__", "spec", "specs", "integrationtest", "integrationtests", "e2e"}


@dataclass(frozen=True)
class TestTarget:
    path: str
    kind: str
    workspace: Path


@dataclass(frozen=True)
class TestCommandSpec:
    language: str
    runner: str
    workspace: str
    command: str
    tests: list[str]


def _is_valid_pytest_target(root: Path, rel_path: str) -> bool:
    target = _classify_test_target(root, rel_path)
    if not target or target.kind != "python":
        return False
    name = Path(target.path).name.lower()
    return name.startswith("test_") or name.endswith("_test.py")


def _is_test_path(rel_path: str) -> bool:
    return is_test_like_path(rel_path)


def _component_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for token in _TOKEN_RE.findall(str(text or "").lower()):
        if token not in {"tests", "test", "src", "core", "spec"}:
            out.add(token)
    return out


def _valid_test_paths(snapshot: HippoSnapshot) -> list[str]:
    root = snapshot.project_root
    test_paths_fn = getattr(snapshot, "test_support_paths", None)
    test_paths = test_paths_fn() if callable(test_paths_fn) else snapshot.first_party_paths()
    out: list[str] = []
    for path in test_paths:
        if _is_test_path(path) and _classify_test_target(root, path):
            out.append(path)
    return out


def _batch_hints(comp_related: list[str], focus_files: list[str], component: str) -> set[str]:
    hints = {Path(path).stem for path in comp_related[:20]}
    hints.update(_component_tokens(component))
    for focus in focus_files:
        hints.update(_component_tokens(Path(str(focus)).stem))
    return hints


def _matching_test_paths(test_paths: list[str], hints: set[str]) -> list[str]:
    matched: list[str] = []
    short_hints = list(hints)[:12]
    for test_path in test_paths:
        low = test_path.lower()
        if any(hint and hint in low for hint in short_hints):
            matched.append(test_path)
    return matched


def _collect_test_candidates(
    snapshot: HippoSnapshot, batches: list[dict[str, Any]]
) -> list[str]:
    comp_files = snapshot.component_files()
    test_paths = _valid_test_paths(snapshot)

    selected: list[str] = []
    seen: set[str] = set()
    for batch in batches:
        comp = str(batch.get("component", ""))
        comp_related = comp_files.get(comp, [])
        focus_files = batch.get("focus_files", []) if isinstance(batch.get("focus_files"), list) else []
        hints = _batch_hints(comp_related, focus_files, comp)
        for test_path in _matching_test_paths(test_paths, hints):
            if test_path not in seen:
                seen.add(test_path)
                selected.append(test_path)
        if len(selected) >= 20:
            break

    return (selected or test_paths[:10])[:20]


def _workspace_for_test(root: Path, rel_test: str) -> Path:
    parts = [seg for seg in str(rel_test or "").split("/") if seg]
    if parts and (root / parts[0]).exists():
        return root / parts[0]
    return root


def _build_pythonpath(root: Path, workspace: Path) -> str:
    roots: list[Path] = []
    for candidate in (workspace / "src", root / "src"):
        if candidate.exists() and candidate not in roots:
            roots.append(candidate)
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if len(roots) >= 8:
            break
        if child.is_dir():
            candidate = child / "src"
            if candidate.exists() and candidate not in roots:
                roots.append(candidate)
    if not roots:
        return ""
    joined = ":".join(str(item) for item in roots)
    return f"PYTHONPATH={shlex.quote(joined)}"


def _normalized_segments(rel_path: str) -> list[str]:
    return [seg.lower() for seg in str(rel_path or "").split("/") if seg]


def _looks_like_jvm_test(parts: list[str], path: Path) -> bool:
    lowered = [seg.lower() for seg in parts]
    if len(lowered) >= 2 and lowered[0] == "src" and lowered[1].startswith("test"):
        return True
    if any(seg in _TEST_DIR_MARKERS for seg in lowered[:-1]):
        return True
    stem = path.stem.lower()
    return stem.endswith(("test", "tests", "itest", "it"))


def _looks_like_native_test(parts: list[str], path: Path) -> bool:
    if any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]):
        return True
    stem = path.stem.lower()
    return (
        stem.startswith(("test_", "spec_", "check_", "verify_"))
        or stem.endswith(("_test", "_spec", "test", "spec"))
    )


def _classify_test_target(root: Path, rel_path: str) -> TestTarget | None:
    path = str(rel_path or "").strip()
    if not path:
        return None
    abs_path = (root / path).resolve()
    if not abs_path.exists() or abs_path.is_dir():
        return None
    if not is_test_like_path(path):
        return None

    suffix = abs_path.suffix.lower()
    name = abs_path.name.lower()
    parts = _normalized_segments(path)
    workspace = _workspace_for_test(root, path)

    if suffix in _PYTHON_SUFFIXES:
        if name.startswith("test_") or name.endswith("_test.py") or any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]):
            return TestTarget(path=path, kind="python", workspace=workspace)
        return None
    if suffix in _NODE_SUFFIXES:
        if ".test." in name or ".spec." in name or any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]):
            return TestTarget(path=path, kind="node", workspace=workspace)
        return None
    if suffix in _GO_SUFFIXES:
        if name.endswith("_test.go"):
            return TestTarget(path=path, kind="go", workspace=workspace)
        return None
    if suffix in _RUST_SUFFIXES:
        if any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]) or "/tests/" in f"/{path.lower()}/":
            return TestTarget(path=path, kind="rust", workspace=workspace)
        return None
    if suffix in _JVM_SUFFIXES:
        if _looks_like_jvm_test(parts, abs_path):
            return TestTarget(path=path, kind="jvm", workspace=workspace)
        return None
    if suffix in _NATIVE_SUFFIXES:
        if _looks_like_native_test(parts, abs_path):
            return TestTarget(path=path, kind="native", workspace=workspace)
        return None
    if suffix in _DOTNET_SUFFIXES:
        if any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]) or any(seg.endswith("tests") for seg in parts[:-1]):
            return TestTarget(path=path, kind="dotnet", workspace=workspace)
        stem = abs_path.stem.lower()
        if stem.endswith(("test", "tests", "integrationtests", "unittests")):
            return TestTarget(path=path, kind="dotnet", workspace=workspace)
        return None
    if suffix in _RUBY_SUFFIXES:
        if name.endswith(("_spec.rb", "_test.rb")) or any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]):
            return TestTarget(path=path, kind="ruby", workspace=workspace)
        return None
    if suffix in _PHP_SUFFIXES:
        if name.endswith("test.php") or any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]):
            return TestTarget(path=path, kind="php", workspace=workspace)
        return None
    if suffix in _DART_SUFFIXES:
        if name.endswith("_test.dart") or any(seg in _TEST_DIR_MARKERS for seg in parts[:-1]):
            return TestTarget(path=path, kind="dart", workspace=workspace)
        return None
    return None


def _group_tests_by_workspace_and_kind(root: Path, tests: list[str]) -> dict[tuple[Path, str], list[str]]:
    grouped: dict[tuple[Path, str], list[str]] = {}
    for test in tests:
        target = _classify_test_target(root, test)
        if not target:
            continue
        grouped.setdefault((target.workspace, target.kind), []).append(target.path)
    return grouped


def _relative_group_tests(root: Path, workspace: Path, tests: list[str]) -> list[str]:
    rel_tests: list[str] = []
    for item in tests[:12]:
        abs_test = (root / item).resolve()
        try:
            rel_tests.append(str(abs_test.relative_to(workspace)))
        except Exception:
            rel_tests.append(item)
    return rel_tests


def _package_manager(workspace: Path) -> str:
    if (workspace / "pnpm-lock.yaml").exists() or (workspace / "pnpm-workspace.yaml").exists():
        return "pnpm"
    if (workspace / "yarn.lock").exists():
        return "yarn"
    if (workspace / "bun.lockb").exists() or (workspace / "bun.lock").exists():
        return "bun"
    return "npm"


def _load_package_json(workspace: Path) -> dict[str, Any]:
    package_json = workspace / "package.json"
    if not package_json.exists():
        return {}
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _node_runner(workspace: Path) -> tuple[str, str]:
    data = _load_package_json(workspace)
    deps = {}
    for key in ("dependencies", "devDependencies"):
        value = data.get(key, {})
        if isinstance(value, dict):
            deps.update({str(k): str(v) for k, v in value.items()})
    pm = _package_manager(workspace)
    has_vitest = "vitest" in deps or any((workspace / name).exists() for name in ("vitest.config.ts", "vitest.config.js", "vite.config.ts", "vite.config.js"))
    has_jest = "jest" in deps or any((workspace / name).exists() for name in ("jest.config.js", "jest.config.ts", "jest.config.cjs"))
    if has_vitest:
        if pm == "pnpm":
            return "vitest", "pnpm exec vitest run"
        if pm == "yarn":
            return "vitest", "yarn vitest run"
        if pm == "bun":
            return "vitest", "bunx vitest run"
        return "vitest", "npx vitest run"
    if has_jest:
        if pm == "pnpm":
            return "jest", "pnpm exec jest --runInBand"
        if pm == "yarn":
            return "jest", "yarn jest --runInBand"
        if pm == "bun":
            return "jest", "bunx jest --runInBand"
        return "jest", "npx jest --runInBand"
    if pm == "pnpm":
        return "package-test", "pnpm test"
    if pm == "yarn":
        return "package-test", "yarn test"
    if pm == "bun":
        return "package-test", "bun test"
    return "package-test", "npm test"


def _runner_language(kind: str) -> str:
    return {
        "python": "python",
        "node": "javascript/typescript",
        "go": "go",
        "rust": "rust",
        "jvm": "java/kotlin",
        "native": "c/cpp/fortran",
        "dotnet": "csharp",
        "ruby": "ruby",
        "php": "php",
        "dart": "dart/flutter",
    }.get(kind, kind)


def _cargo_command_for_tests(rel_tests: list[str]) -> str:
    test_bins = []
    for path in rel_tests:
        p = Path(path)
        parts = [seg.lower() for seg in p.parts]
        if parts and parts[0] == "tests":
            test_bins.append(p.stem)
    if test_bins:
        return " && ".join(f"cargo test --test {shlex.quote(name)}" for name in test_bins[:6])
    return "cargo test"


def _jvm_command(workspace: Path, rel_tests: list[str]) -> str:
    class_names = [Path(path).stem for path in rel_tests[:8]]
    if (workspace / "gradlew").exists():
        selectors = " ".join(f"--tests {shlex.quote(name)}" for name in class_names)
        return f"./gradlew test {selectors}".strip()
    if (workspace / "mvnw").exists():
        joined = ",".join(class_names)
        return f"./mvnw -q -Dtest={shlex.quote(joined)} test"
    if (workspace / "pom.xml").exists():
        joined = ",".join(class_names)
        return f"mvn -q -Dtest={shlex.quote(joined)} test"
    return "./gradlew test" if (workspace / "build.gradle").exists() or (workspace / "build.gradle.kts").exists() else "mvn test"


def _native_command(workspace: Path, rel_tests: list[str]) -> str:
    names = [Path(path).stem for path in rel_tests[:8]]
    if (workspace / "fpm.toml").exists():
        return "fpm test"
    if (workspace / "CMakeLists.txt").exists() or (workspace / "CTestTestfile.cmake").exists():
        if names:
            pattern = "|".join(re.escape(name) for name in names)
            return f"ctest --output-on-failure -R {shlex.quote(pattern)}"
        return "ctest --output-on-failure"
    if (workspace / "meson.build").exists():
        return "meson test -C build"
    if (workspace / "Makefile").exists() or (workspace / "makefile").exists():
        return "make test"
    return "ctest --output-on-failure"


def _dotnet_command(workspace: Path, rel_tests: list[str]) -> str:
    names = [Path(path).stem for path in rel_tests[:8]]
    if names:
        filter_expr = "|".join(f"FullyQualifiedName~{name}" for name in names)
        return f"dotnet test --filter {shlex.quote(filter_expr)}"
    return "dotnet test"


def _ruby_commands(rel_tests: list[str]) -> list[str]:
    spec_tests = [path for path in rel_tests if path.endswith("_spec.rb") or "/spec/" in f"/{path.lower()}/"]
    unit_tests = [path for path in rel_tests if path not in spec_tests]
    cmds: list[str] = []
    if spec_tests:
        chunk = " ".join(shlex.quote(path) for path in spec_tests)
        cmds.append(f"bundle exec rspec {chunk}")
    for path in unit_tests[:8]:
        cmds.append(f"bundle exec ruby -Itest {shlex.quote(path)}")
    return cmds


def _php_command(workspace: Path, rel_tests: list[str]) -> str:
    runner = "vendor/bin/phpunit" if (workspace / "vendor" / "bin" / "phpunit").exists() else "phpunit"
    chunk = " ".join(shlex.quote(path) for path in rel_tests)
    return f"{runner} {chunk}".strip()


def _dart_command(workspace: Path, rel_tests: list[str]) -> str:
    runner = "dart test"
    pubspec = workspace / "pubspec.yaml"
    if pubspec.exists():
        try:
            text = pubspec.read_text(encoding="utf-8", errors="ignore").lower()
            if "flutter:" in text:
                runner = "flutter test"
        except Exception:
            pass
    chunk = " ".join(shlex.quote(path) for path in rel_tests)
    return f"{runner} {chunk}".strip()


def _build_commands_for_group(root: Path, workspace: Path, kind: str, tests: list[str]) -> list[str]:
    return [spec.command for spec in _build_command_specs_for_group(root, workspace, kind, tests)]


def _build_command_specs_for_group(root: Path, workspace: Path, kind: str, tests: list[str]) -> list[TestCommandSpec]:
    rel_tests = _relative_group_tests(root, workspace, tests)
    language = _runner_language(kind)
    if kind == "python":
        chunk = " ".join(shlex.quote(p) for p in rel_tests)
        py = _build_pythonpath(root, workspace)
        if py:
            return [TestCommandSpec(language=language, runner="pytest", workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {py} pytest -q {chunk}", tests=rel_tests)]
        return [TestCommandSpec(language=language, runner="pytest", workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && pytest -q {chunk}", tests=rel_tests)]
    if kind == "node":
        runner_name, base = _node_runner(workspace)
        chunk = " ".join(shlex.quote(p) for p in rel_tests)
        if base.endswith("test"):
            return [TestCommandSpec(language=language, runner=runner_name, workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {base}", tests=rel_tests)]
        return [TestCommandSpec(language=language, runner=runner_name, workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {base} {chunk}".strip(), tests=rel_tests)]
    if kind == "go":
        dirs = sorted({str(Path(path).parent) for path in rel_tests})[:8]
        return [
            TestCommandSpec(
                language=language,
                runner="go test",
                workspace=str(workspace),
                command=f"cd {shlex.quote(str(workspace))} && go test ./{shlex.quote(d)}",
                tests=[path for path in rel_tests if str(Path(path).parent) == d],
            )
            for d in dirs
        ]
    if kind == "rust":
        return [TestCommandSpec(language=language, runner="cargo test", workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {_cargo_command_for_tests(rel_tests)}", tests=rel_tests)]
    if kind == "jvm":
        command = _jvm_command(workspace, rel_tests)
        runner = "gradle" if "gradlew" in command or "gradle" in command else "maven"
        return [TestCommandSpec(language=language, runner=runner, workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {command}", tests=rel_tests)]
    if kind == "native":
        command = _native_command(workspace, rel_tests)
        runner = command.split()[0]
        return [TestCommandSpec(language=language, runner=runner, workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {command}", tests=rel_tests)]
    if kind == "dotnet":
        return [TestCommandSpec(language=language, runner="dotnet test", workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {_dotnet_command(workspace, rel_tests)}", tests=rel_tests)]
    if kind == "ruby":
        specs: list[TestCommandSpec] = []
        for cmd in _ruby_commands(rel_tests):
            runner = "rspec" if "rspec" in cmd else "ruby"
            specs.append(TestCommandSpec(language=language, runner=runner, workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {cmd}", tests=rel_tests))
        return specs
    if kind == "php":
        return [TestCommandSpec(language=language, runner="phpunit", workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {_php_command(workspace, rel_tests)}", tests=rel_tests)]
    if kind == "dart":
        command = _dart_command(workspace, rel_tests)
        runner = "flutter test" if command.startswith("flutter ") else "dart test"
        return [TestCommandSpec(language=language, runner=runner, workspace=str(workspace), command=f"cd {shlex.quote(str(workspace))} && {command}", tests=rel_tests)]
    return []


def _build_test_commands(root: Path, tests: list[str]) -> list[str]:
    return [spec["command"] for spec in _build_test_command_specs(root, tests)]


def _build_test_command_specs(root: Path, tests: list[str]) -> list[dict[str, Any]]:
    if not tests:
        return []
    valid_tests = [t for t in tests if _classify_test_target(root, t)]
    if not valid_tests:
        return []

    grouped = _group_tests_by_workspace_and_kind(root, valid_tests)
    specs: list[dict[str, Any]] = []
    for (workspace, kind), group_tests in sorted(grouped.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        specs.extend(spec.__dict__ for spec in _build_command_specs_for_group(root, workspace, kind, group_tests))
    return specs


def _run_test_commands(commands: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for cmd in commands:
        proc = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        results.append(
            {
                "command": cmd,
                "exit_code": proc.returncode,
                "passed": proc.returncode == 0,
                "output_tail": "\n".join(out.splitlines()[-80:]),
            }
        )
    return results
