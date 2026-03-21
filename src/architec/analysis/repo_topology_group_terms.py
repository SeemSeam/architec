from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Any

from architec.integration.hippo_adapter import HippoSnapshot
from architec.support.io_utils import normalize_relpath


def _descriptor_term_counts(
    descriptor: dict[str, Any],
    *,
    term_generic: set[str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for term in descriptor.get('descriptor_terms', [])[:12]:
        token = str(term or '').strip().lower()
        if len(token) >= 4 and token not in term_generic:
            counts[token] += 3
    return counts


def _stem_term_counts(
    path: str,
    *,
    term_generic: set[str],
    stem_tokens_fn,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for token in stem_tokens_fn(path):
        if len(token) >= 4 and token not in term_generic:
            counts[token] += 2
    return counts


def _signature_term_counts(
    snapshot: HippoSnapshot,
    path: str,
    *,
    term_generic: set[str],
    tokenize_symbol_fn,
    seen_symbols: set[str],
    symbols: list[str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for signature in snapshot.signatures_for_file(path)[:6]:
        name = str(signature.get('name', '') or '').strip()
        if not name:
            continue
        if name not in seen_symbols and len(symbols) < 8:
            seen_symbols.add(name)
            symbols.append(name)
        for token in tokenize_symbol_fn(name):
            if token not in term_generic:
                counts[token] += 1
    return counts


def group_terms(
    snapshot: HippoSnapshot,
    files: list[str],
    *,
    path_to_descriptor: dict[str, dict[str, Any]],
    term_generic: set[str],
    stem_tokens_fn,
    tokenize_symbol_fn,
) -> tuple[list[str], list[str], list[str]]:
    term_counts: Counter[str] = Counter()
    symbols: list[str] = []
    summaries: list[str] = []
    seen_symbols: set[str] = set()
    seen_summaries: set[str] = set()

    for path in files:
        descriptor = path_to_descriptor.get(path, {})
        term_counts.update(
            _descriptor_term_counts(descriptor, term_generic=term_generic)
        )
        summary = str(descriptor.get('responsibility_summary', '') or '').strip()
        if summary and summary not in seen_summaries and len(summaries) < 3:
            seen_summaries.add(summary)
            summaries.append(summary)
        term_counts.update(
            _stem_term_counts(
                path,
                term_generic=term_generic,
                stem_tokens_fn=stem_tokens_fn,
            )
        )
        term_counts.update(
            _signature_term_counts(
                snapshot,
                path,
                term_generic=term_generic,
                tokenize_symbol_fn=tokenize_symbol_fn,
                seen_symbols=seen_symbols,
                symbols=symbols,
            )
        )

    return [term for term, _ in term_counts.most_common(8)], symbols[:6], summaries[:2]


def secondary_token_share(files: list[str], *, stem_tokens_fn) -> float:
    secondary = [
        tokens[1]
        for path in files
        for tokens in [stem_tokens_fn(path)]
        if len(tokens) >= 2
    ]
    if not secondary:
        return 1.0
    counts = Counter(secondary)
    return counts.most_common(1)[0][1] / max(1, len(secondary))


def group_folder_votes(
    files: list[str],
    *,
    path_to_descriptor: dict[str, dict[str, Any]],
    file_folder_vote_fn,
) -> dict[str, int]:
    votes: Counter[str] = Counter()
    for path in files:
        folder, _, _ = file_folder_vote_fn(path, path_to_descriptor=path_to_descriptor)
        if folder:
            votes[folder] += 1
    return dict(votes)


def _parsed_module(project_root: Path, path: str) -> ast.AST | None:
    root = project_root / normalize_relpath(path)
    try:
        source = root.read_text(encoding='utf-8')
    except Exception:
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _package_name(source_root: str) -> str:
    parts = [part for part in normalize_relpath(source_root).split('/') if part]
    return parts[-1] if parts else ''


def _import_targets(tree: ast.AST, package_name: str) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _collect_import_targets(targets, node, package_name)
            continue
        if isinstance(node, ast.ImportFrom):
            _collect_from_targets(targets, node, package_name)
    return targets


def _collect_import_targets(
    targets: set[str],
    node: ast.Import,
    package_name: str,
) -> None:
    for alias in node.names:
        name = str(alias.name or '').strip()
        if package_name and name.startswith(f'{package_name}.'):
            targets.add(name.split('.', 1)[1])


def _collect_from_targets(
    targets: set[str],
    node: ast.ImportFrom,
    package_name: str,
) -> None:
    module = str(node.module or '').strip()
    if node.level >= 1:
        if module:
            targets.add(module)
            return
        for alias in node.names:
            alias_name = str(alias.name or '').strip()
            if alias_name:
                targets.add(alias_name)
        return
    if package_name and module.startswith(f'{package_name}.'):
        targets.add(module.split('.', 1)[1])


def module_import_signals(project_root: Path, path: str, source_root: str) -> dict[str, Any]:
    tree = _parsed_module(project_root, path)
    if tree is None:
        return {'internal_import_total': 0, 'internal_targets': []}
    targets = sorted(_import_targets(tree, _package_name(source_root)))
    return {
        'internal_import_total': len(targets),
        'internal_targets': targets[:8],
    }
