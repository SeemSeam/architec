from __future__ import annotations

from html import escape
from typing import Any


def score_card(label: str, value: Any, *, primary: bool = False) -> str:
    klass = 'score-card primary' if primary else 'score-card'
    return (
        f'<div class="{klass}"><div class="score-label">{escape(label)}</div>'
        f'<div class="score-value">{escape(str(value))}</div></div>'
    )


def hero_mode(meta: dict[str, Any]) -> str:
    return escape(str(meta.get("mode", "full")))


def hero_path(meta: dict[str, Any]) -> str:
    return escape(str(meta.get("path", "")))


def hero_headline(summary: dict[str, Any]) -> str:
    return escape(str(summary.get("headline", "Architecture snapshot")))


def hero_summary(summary: dict[str, Any]) -> str:
    return escape(str(summary.get("executive_summary", "")))


def score_grid(scores: dict[str, Any]) -> str:
    return ''.join(
        [
            score_card('Structure', scores.get('structure', 0.0), primary=True),
            score_card('Overall', scores.get('overall', 0.0)),
            score_card('Full', scores.get('full', 0.0)),
            score_card('Incremental', scores.get('incremental', 0.0)),
        ]
    )


def empty_state(text: str) -> str:
    return f'<p class="muted">{text}</p>'
