from __future__ import annotations

import json
from html import escape
from typing import Any, Callable


def structure_bars(structure_dimensions: dict[str, Any]) -> str:
    rows: list[str] = []
    for name, value in list(structure_dimensions.items())[:4]:
        width = max(0.0, min(100.0, float(value or 0.0)))
        rows.append(
            '<div class="bar-row">'
            f'<span>{escape(str(name).replace("_", " ").title())}</span>'
            f'<div class="bar"><div class="bar-fill" style="width:{width}%"></div></div>'
            f'<strong>{escape(str(value))}</strong>'
            '</div>'
        )
    return ''.join(rows)


def label_text(labels: object) -> str:
    if not isinstance(labels, list):
        return ''
    return ' / '.join(escape(str(label)) for label in labels[:3])


def item_cards(
    items: list[dict[str, Any]],
    *,
    title_key: str,
    body_text: Callable[[dict[str, Any]], str],
    small_text: Callable[[dict[str, Any]], object],
) -> str:
    cards: list[str] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        cards.append(
            '<div class="item-card">'
            f'<h3>{escape(str(item.get(title_key, "")))}</h3>'
            f'<p>{body_text(item)}</p>'
            f'<small>{escape(str(small_text(item)))}</small>'
            '</div>'
        )
    return ''.join(cards)


def graph_block(graph_nodes: list[dict[str, Any]], graph_edges: list[dict[str, Any]]) -> str:
    if not graph_nodes or not graph_edges:
        return ''
    payload = escape(
        json.dumps({'nodes': graph_nodes, 'edges': graph_edges}, ensure_ascii=False)
    )
    return (
        '<section class="section"><h2>Hotspot Graph</h2>'
        '<p class="muted">Local component relationship snapshot for current hotspots.</p>'
        f'<pre class="graph-dump">{payload}</pre></section>'
    )
