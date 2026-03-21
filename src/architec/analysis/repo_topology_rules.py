from __future__ import annotations

from pathlib import Path
import re

from .repo_topology_rule_data import (
    DOMAIN_ALIAS,
    FILE_FOLDER_HINTS,
    GROUP_PREFIXES,
    PREFERRED_FOLDER_ALTERNATIVES,
    TERM_FOLDER_RULES,
    TERM_GENERIC,
)

CAMEL_BREAK_RE = re.compile(r'(?<!^)(?=[A-Z])')


def stem_tokens(path: str) -> list[str]:
    stem = Path(path).stem.lower()
    return [token for token in stem.split('_') if token]


def domain_token(path: str) -> str:
    stem = Path(path).stem.lower()
    if not stem:
        return 'misc'
    for prefix, group_id in GROUP_PREFIXES:
        if stem == prefix or stem.startswith(f'{prefix}_'):
            return group_id
    tokens = stem_tokens(path)
    if not tokens:
        return 'misc'
    first = tokens[0]
    if first in {'backend', 'scoring', 'architecture'} and len(tokens) >= 2:
        return '_'.join(tokens[:2])
    return first


def preferred_folder_name(group_id: str, terms: list[str]) -> tuple[str, list[str]]:
    raw = str(group_id or '').strip().lower()
    base = DOMAIN_ALIAS.get(raw, raw.replace('_llm', '') or 'module')
    preferred = PREFERRED_FOLDER_ALTERNATIVES.get(raw)
    if preferred is not None:
        return preferred[0], list(preferred[1])
    alternatives = [base]
    if raw not in alternatives:
        alternatives.append(raw)
    return base, alternatives


def tokenize_symbol(text: str) -> list[str]:
    spaced = CAMEL_BREAK_RE.sub(' ', str(text or ''))
    tokens: list[str] = []
    current = []
    for char in spaced:
        if char.isalnum():
            current.append(char.lower())
            continue
        if current:
            tokens.append(''.join(current))
            current = []
    if current:
        tokens.append(''.join(current))
    return [token for token in tokens if len(token) >= 4]


def descriptor_terms_for_path(
    path: str,
    path_to_descriptor: dict[str, dict[str, object]],
) -> list[str]:
    descriptor = path_to_descriptor.get(path, {})
    raw = descriptor.get('descriptor_terms', []) if isinstance(descriptor, dict) else []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw[:12]:
        token = str(item or '').strip().lower()
        if token:
            out.append(token)
    return out


def match_folder_hint(stem: str) -> tuple[str, list[str], float] | None:
    for prefix, folder in FILE_FOLDER_HINTS.items():
        if stem == prefix or stem.startswith(f'{prefix}_'):
            alternatives = [folder]
            if folder != prefix:
                alternatives.append(prefix)
            confidence = 0.9 if folder == prefix else 0.84
            return folder, alternatives[:3], confidence
    return None


def match_term_folder_rule(terms: set[str]) -> tuple[str, list[str], float] | None:
    for candidates, folder, alternatives, confidence in TERM_FOLDER_RULES:
        if terms & candidates:
            return folder, list(alternatives), confidence
    if 'llm' in terms and {'guard', 'preflight'} & terms:
        return 'support', ['support', 'llm_support'], 0.66
    return None


def file_folder_vote(
    path: str,
    *,
    path_to_descriptor: dict[str, dict[str, object]],
) -> tuple[str, list[str], float]:
    stem = Path(path).stem.lower()
    terms = set(descriptor_terms_for_path(path, path_to_descriptor))
    hinted = match_folder_hint(stem)
    if hinted is not None:
        return hinted
    term_match = match_term_folder_rule(terms)
    if term_match is not None:
        return term_match
    group_id = domain_token(path)
    folder, alternatives = preferred_folder_name(group_id, list(terms))
    confidence = 0.72 if group_id not in {'misc', 'component', 'report', 'paths'} else 0.55
    return folder, alternatives[:3], confidence
