from __future__ import annotations

import json
from html import escape
from typing import Any


def _score_card(label: str, value: Any, *, primary: bool = False) -> str:
    klass = 'score-card primary' if primary else 'score-card'
    return (
        f'<div class="{klass}"><div class="score-label">{escape(label)}</div>'
        f'<div class="score-value">{escape(str(value))}</div></div>'
    )


def render_viz_html(report: dict[str, Any]) -> str:
    meta = report.get('meta', {}) if isinstance(report.get('meta'), dict) else {}
    scores = report.get('scores', {}) if isinstance(report.get('scores'), dict) else {}
    summary = report.get('summary', {}) if isinstance(report.get('summary'), dict) else {}
    hotspots = report.get('hotspots', []) if isinstance(report.get('hotspots'), list) else []
    components = report.get('components', []) if isinstance(report.get('components'), list) else []
    recommendations = report.get('recommendations', []) if isinstance(report.get('recommendations'), list) else []
    structure_dimensions = scores.get('structure_dimensions', {}) if isinstance(scores.get('structure_dimensions'), dict) else {}
    graph = report.get('graph', {}) if isinstance(report.get('graph'), dict) else {}
    graph_nodes = graph.get('nodes', []) if isinstance(graph.get('nodes'), list) else []
    graph_edges = graph.get('edges', []) if isinstance(graph.get('edges'), list) else []

    structure_bars = ''.join(
        f'<div class="bar-row"><span>{escape(str(name).replace("_", " ").title())}</span>'
        f'<div class="bar"><div class="bar-fill" style="width:{max(0.0, min(100.0, float(value or 0.0)))}%"></div></div>'
        f'<strong>{escape(str(value))}</strong></div>'
        for name, value in list(structure_dimensions.items())[:4]
    )
    hotspot_cards = ''.join(
        f'<div class="item-card"><h3>{escape(str(item.get("path", "")))}</h3>'
        f'<p>{escape(str(item.get("reason", "")))}</p>'
        f'<small>{escape(str(item.get("structure_impact", "")))}</small></div>'
        for item in hotspots[:5]
        if isinstance(item, dict)
    )
    component_cards = ''.join(
        f'<div class="item-card"><h3>{escape(str(item.get("component", "")))}</h3>'
        f'<p>{" / ".join(escape(str(label)) for label in item.get("labels", [])[:3])}</p>'
        f'<small>risk={escape(str(item.get("risk_score", 0.0)))}</small></div>'
        for item in components[:5]
        if isinstance(item, dict)
    )
    recommendation_cards = ''.join(
        f'<div class="item-card"><h3>{escape(str(item.get("title", "")))}</h3>'
        f'<p>{escape(str(item.get("why", "")))}</p>'
        f'<small>{escape(str(item.get("scope", "")))}</small></div>'
        for item in recommendations[:5]
        if isinstance(item, dict)
    )
    graph_block = ''
    if graph_nodes and graph_edges:
        payload = escape(json.dumps({'nodes': graph_nodes, 'edges': graph_edges}, ensure_ascii=False))
        graph_block = (
            '<section class="section"><h2>Hotspot Graph</h2>'
            '<p class="muted">Local component relationship snapshot for current hotspots.</p>'
            f'<pre class="graph-dump">{payload}</pre></section>'
        )

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Architec</title>
  <style>
    :root {{ --bg:#f4f1e8; --panel:#fffdf8; --ink:#182126; --muted:#566068; --accent:#c74f2f; --line:#d7cfbf; }}
    body {{ margin:0; font-family:Georgia, "Times New Roman", serif; background:linear-gradient(180deg,#efe7d5 0%,var(--bg) 45%,#f8f5ee 100%); color:var(--ink); }}
    .wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 48px; }}
    .hero, .section {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:22px; box-shadow:0 8px 28px rgba(24,33,38,.06); }}
    .hero h1, .section h2 {{ margin:0 0 12px; }}
    .score-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:18px 0 10px; }}
    .score-card {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:#faf7f0; }}
    .score-card.primary {{ background:#fff1eb; border-color:#e0a692; }}
    .score-label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .score-value {{ font-size:34px; font-weight:700; margin-top:8px; }}
    .muted {{ color:var(--muted); }}
    .layout {{ display:grid; gap:16px; margin-top:16px; }}
    .bar-row {{ display:grid; grid-template-columns:170px 1fr 56px; gap:12px; align-items:center; margin:10px 0; }}
    .bar {{ height:10px; background:#ece4d6; border-radius:999px; overflow:hidden; }}
    .bar-fill {{ height:100%; background:linear-gradient(90deg,#d48056,#c74f2f); }}
    .item-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; }}
    .item-card {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:#fff; }}
    .item-card h3 {{ margin:0 0 8px; font-size:16px; word-break:break-word; }}
    .item-card p {{ margin:0 0 8px; color:var(--muted); font-size:14px; }}
    .graph-dump {{ white-space:pre-wrap; word-break:break-word; font-size:12px; background:#f8f4ea; padding:12px; border-radius:12px; border:1px solid var(--line); }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="muted">Architec · {escape(str(meta.get("mode", "full")))} · {escape(str(meta.get("path", "")))}</div>
      <h1>{escape(str(summary.get("headline", "Architecture snapshot")))}</h1>
      <p>{escape(str(summary.get("executive_summary", "")))}</p>
      <div class="score-grid">
        {_score_card('Structure', scores.get('structure', 0.0), primary=True)}
        {_score_card('Overall', scores.get('overall', 0.0))}
        {_score_card('Full', scores.get('full', 0.0))}
        {_score_card('Incremental', scores.get('incremental', 0.0))}
      </div>
    </section>
    <div class="layout">
      <section class="section"><h2>Structure Signals</h2>{structure_bars or '<p class="muted">No structure signals.</p>'}</section>
      <section class="section"><h2>Top Hotspots</h2><div class="item-grid">{hotspot_cards or '<p class="muted">No hotspots.</p>'}</div></section>
      <section class="section"><h2>Risk Components</h2><div class="item-grid">{component_cards or '<p class="muted">No risk components.</p>'}</div></section>
      <section class="section"><h2>Recommendations</h2><div class="item-grid">{recommendation_cards or '<p class="muted">No recommendations.</p>'}</div></section>
      {graph_block}
    </div>
  </div>
</body>
</html>
'''
