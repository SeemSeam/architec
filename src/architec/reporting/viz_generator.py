from __future__ import annotations

from html import escape
from typing import Any

from architec.reporting.viz_generator_view import viz_content
from architec.reporting.viz_generator_sections import (
    empty_state,
    hero_headline,
    hero_mode,
    hero_path,
    hero_summary,
    score_grid,
)


def _report_section(report: dict[str, Any], key: str, expected_type: type) -> Any:
    value = report.get(key, expected_type())
    return value if isinstance(value, expected_type) else expected_type()


def render_viz_html(report: dict[str, Any]) -> str:
    meta = _report_section(report, 'meta', dict)
    scores = _report_section(report, 'scores', dict)
    summary = _report_section(report, 'summary', dict)
    topology = _report_section(report, 'topology', dict)
    content = viz_content(report)
    score_cards = score_grid(scores)

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Architec</title>
  <style>
    :root {{
      --bg:#f4f1e8; --panel:#fffdf8; --ink:#182126; --muted:#566068;
      --accent:#c74f2f; --line:#d7cfbf;
    }}
    body {{
      margin:0; font-family:Georgia, "Times New Roman", serif;
      background:linear-gradient(180deg,#efe7d5 0%,var(--bg) 45%,#f8f5ee 100%);
      color:var(--ink);
    }}
    .wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 48px; }}
    .hero, .section {{
      background:var(--panel); border:1px solid var(--line); border-radius:18px;
      padding:22px; box-shadow:0 8px 28px rgba(24,33,38,.06);
    }}
    .hero h1, .section h2 {{ margin:0 0 12px; }}
    .score-grid {{
      display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
      gap:12px; margin:18px 0 10px;
    }}
    .score-card {{
      border:1px solid var(--line); border-radius:14px;
      padding:14px; background:#faf7f0;
    }}
    .score-card.primary {{ background:#fff1eb; border-color:#e0a692; }}
    .score-label {{
      color:var(--muted); font-size:12px;
      text-transform:uppercase; letter-spacing:.08em;
    }}
    .score-value {{ font-size:34px; font-weight:700; margin-top:8px; }}
    .muted {{ color:var(--muted); }}
    .layout {{ display:grid; gap:16px; margin-top:16px; }}
    .bar-row {{
      display:grid; grid-template-columns:170px 1fr 56px;
      gap:12px; align-items:center; margin:10px 0;
    }}
    .bar {{ height:10px; background:#ece4d6; border-radius:999px; overflow:hidden; }}
    .bar-fill {{ height:100%; background:linear-gradient(90deg,#d48056,#c74f2f); }}
    .item-grid {{
      display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
      gap:12px;
    }}
    .item-card {{
      border:1px solid var(--line); border-radius:14px;
      padding:14px; background:#fff;
    }}
    .item-card h3 {{ margin:0 0 8px; font-size:16px; word-break:break-word; }}
    .item-card p {{ margin:0 0 8px; color:var(--muted); font-size:14px; }}
    .graph-dump {{
      white-space:pre-wrap; word-break:break-word; font-size:12px;
      background:#f8f4ea; padding:12px; border-radius:12px;
      border:1px solid var(--line);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="muted">Architec · {hero_mode(meta)} · {hero_path(meta)}</div>
      <h1>{hero_headline(summary)}</h1>
      <p>{hero_summary(summary)}</p>
      <div class="score-grid">{score_cards}</div>
    </section>
      <div class="layout">
      <section class="section">
        <h2>Structure Signals</h2>
        {content['structure_bar_markup'] or empty_state('No structure signals.')}
      </section>
      <section class="section">
        <h2>Top Hotspots</h2>
        <div class="item-grid">{content['hotspot_cards'] or empty_state('No hotspots.')}</div>
      </section>
      <section class="section">
        <h2>Risk Components</h2>
        <div class="item-grid">{content['component_cards'] or empty_state('No risk components.')}</div>
      </section>
      <section class="section">
        <h2>Recommendations</h2>
        <div class="item-grid">{content['recommendation_cards'] or empty_state('No recommendations.')}</div>
      </section>
      <section class="section">
        <h2>Folder Management</h2>
        <p class="muted">{content['topology_summary']}</p>
        <p class="muted">{content['root_placement_summary']}</p>
        <div class="item-grid">{content['topology_cards'] or empty_state('No folder review groups.')}</div>
      </section>
      <section class="section">
        <h2>Migration Plan</h2>
        <p class="muted">{content['migration_summary']}</p>
        <div class="item-grid">{content['migration_cards'] or empty_state('No file moves proposed.')}</div>
      </section>
      {content['graph_markup']}
    </div>
  </div>
</body>
</html>
'''
