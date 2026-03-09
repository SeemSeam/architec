from __future__ import annotations

import ast
from typing import Any


def calc_cyclomatic(fn: ast.AST) -> int:
    score = 1
    for node in ast.walk(fn):
        if isinstance(
            node,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.With,
                ast.AsyncWith,
                ast.IfExp,
                ast.ExceptHandler,
                ast.Match,
            ),
        ):
            score += 1
            continue
        if isinstance(node, ast.BoolOp):
            score += max(0, len(node.values) - 1)
            continue
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            score += len(node.generators)
            for gen in node.generators:
                score += len(gen.ifs)
            continue
        if isinstance(node, ast.Try):
            score += len(node.handlers)
            if node.orelse:
                score += 1
            if node.finalbody:
                score += 1
    return score


def collect_self_attrs(tree: ast.ClassDef) -> set[str]:
    attrs: set[str] = set()
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Assign):
            for candidate in node.targets:
                if isinstance(candidate, ast.Attribute):
                    target = candidate
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute):
            target = node.target
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id == "self":
                attrs.add(target.attr)
    return attrs


def extract_import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root:
                    roots.add(root)
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root:
                roots.add(root)
    return roots


def _function_findings(node: ast.AST, *, rel: str, thr) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cc = calc_cyclomatic(node)
    if cc > thr.cc_hard:
        findings.append(
            {
                "id": "cyclomatic_hard",
                "dimension": "complexity",
                "severity": "critical",
                "path": rel,
                "symbol": node.name,
                "metric": "cyclomatic_complexity",
                "value": cc,
                "threshold": thr.cc_hard,
                "message": "Function exceeds hard cyclomatic complexity threshold.",
            }
        )
    elif cc > thr.cc_soft:
        findings.append(
            {
                "id": "cyclomatic_soft",
                "dimension": "complexity",
                "severity": "warning",
                "path": rel,
                "symbol": node.name,
                "metric": "cyclomatic_complexity",
                "value": cc,
                "threshold": thr.cc_soft,
                "message": "Function exceeds soft cyclomatic complexity threshold.",
            }
        )
    return findings


def _class_findings(node: ast.ClassDef, *, rel: str, thr) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    public_methods = [
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_")
    ]
    attrs = collect_self_attrs(node)

    if len(public_methods) > thr.class_methods_soft:
        findings.append(
            {
                "id": "class_public_methods_soft",
                "dimension": "encapsulation",
                "severity": "warning",
                "path": rel,
                "symbol": node.name,
                "metric": "class_public_methods",
                "value": len(public_methods),
                "threshold": thr.class_methods_soft,
                "message": "Class has too many public methods (god-object risk).",
            }
        )

    if len(attrs) > thr.class_attrs_soft:
        findings.append(
            {
                "id": "class_instance_attrs_soft",
                "dimension": "encapsulation",
                "severity": "warning",
                "path": rel,
                "symbol": node.name,
                "metric": "class_instance_attributes",
                "value": len(attrs),
                "threshold": thr.class_attrs_soft,
                "message": "Class has many instance attributes (encapsulation risk).",
            }
        )
    return findings


def analyze_python_file(*, rel: str, text: str, thr) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {
            "imports": set(),
            "function_count": 0,
            "class_count": 0,
            "findings": [
                {
                    "id": "python_parse_error",
                    "dimension": "complexity",
                    "severity": "warning",
                    "path": rel,
                    "message": "Python file failed to parse; complexity metrics unavailable.",
                }
            ],
        }

    findings: list[dict[str, Any]] = []
    function_count = 0
    class_count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_count += 1
            findings.extend(_function_findings(node, rel=rel, thr=thr))
            continue
        if isinstance(node, ast.ClassDef):
            class_count += 1
            findings.extend(_class_findings(node, rel=rel, thr=thr))

    return {
        "imports": extract_import_roots(tree),
        "function_count": function_count,
        "class_count": class_count,
        "findings": findings,
    }

