from __future__ import annotations

from pathlib import Path


ARCHITEC_DIR = Path('.architec')
ANALYSIS_JSON_PATH = ARCHITEC_DIR / 'architec-analysis.json'
SUMMARY_MD_PATH = ARCHITEC_DIR / 'architec-summary.md'
VIZ_HTML_PATH = ARCHITEC_DIR / 'architec-viz.html'
ANALYSIS_CACHE_DIR = ARCHITEC_DIR / 'cache' / 'analysis'
BACKEND_LLM_CACHE_PATH = ARCHITEC_DIR / 'cache' / 'backend-llm.json'
REFRESH_STATE_PATH = ARCHITEC_DIR / 'architec-refresh-state.json'
HISTORY_REPORT_PATH = ARCHITEC_DIR / 'architec-history-report.json'
DEBT_LEDGER_PATH = ARCHITEC_DIR / 'architec-debt-ledger.json'
FEATURE_REPORT_PATH = ARCHITEC_DIR / 'architec-feature-suggestion.json'
SCORE_REPORT_PATH = ARCHITEC_DIR / 'architec-component-score.json'
REGISTRY_PATH = ARCHITEC_DIR / 'architec-component-registry.json'
QA_REPORT_PATH = ARCHITEC_DIR / 'architec-component-qa.json'
HOTSPOT_DIGEST_PATH = ARCHITEC_DIR / 'architec-hotspots-topk.json'
COMPONENT_DESCRIPTOR_PATH = ARCHITEC_DIR / 'architec-component-descriptors.json'
ARCHITECTURE_REPORT_MD_PATH = ARCHITEC_DIR / 'architec-architecture-report.md'
