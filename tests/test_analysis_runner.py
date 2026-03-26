from __future__ import annotations

import json
from pathlib import Path

import architec.analysis_runner as runner


class _Snapshot:
    def __init__(self, root: Path):
        self.project_root = root
        self.metrics = {'findings': []}
        self.index = {'files': {'a.py': {}, 'b.py': {}}}
        self.signatures = {'files': {}}

    def first_party_paths(self):
        return ['a.py', 'b.py']

    def first_party_findings(self):
        return []


def test_run_analysis_writes_architec_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.HippoSnapshot, 'load', lambda root: _Snapshot(root))
    monkeypatch.setattr(
        runner,
        'analyze_history_and_iterate',
        lambda root, llm_enabled=True: {
            'full_score': {'score': 82.0},
            'summary': {'by_metric': {'module_lines': 2}, 'by_dimension': {'boundary': 1}, 'by_severity': {'warning': 2}},
            'component_risk': {'core': {'risk_score': 7.5, 'critical': 0, 'warning': 2, 'file_count': 3}},
        },
    )
    monkeypatch.setattr(runner, 'suggest_feature_architecture', lambda *args, **kwargs: {'target_components': [], 'candidate_files': []})
    monkeypatch.setattr(runner, 'score_changed_components', lambda *args, **kwargs: {'incremental_score': {'score': 91.0}, 'changed_file_total': 1, 'components': []})
    monkeypatch.setattr(
        runner,
        'build_hotspot_digest',
        lambda *args, **kwargs: {
            'items': [
                {
                    'rank': 1,
                    'path': 'a.py',
                    'component': 'core',
                    'fix_hint': 'Split module',
                    'dominant_metric': 'module_lines',
                }
            ]
        },
    )
    monkeypatch.setattr(runner, '_llm_summary', lambda *args, **kwargs: {'headline': 'Snapshot', 'executive_summary': 'Main issues are concentrated in core.'})
    monkeypatch.setattr(
        runner,
        '_review_folder_topology',
        lambda *args, **kwargs: {
            'source_root': 'src/architec',
            'flat_file_total': 24,
            'subpackage_total': 0,
            'flatness_score': 58.0,
            'summary': 'src/architec remains flat.',
            'needs_folder_management': True,
            'findings': [{'severity': 'warning', 'kind': 'root_flatness', 'detail': 'flat root'}],
            'root_placement_review': {
                'misplaced_root_files': [{'path': 'io_utils.py'}],
                'review_root_files': [{'path': 'paths.py'}],
            },
            'groups': [
                {
                    'group_id': 'backend_llm',
                    'file_count': 3,
                    'programmatic_name': 'backend_llm',
                    'candidate_files': ['a.py', 'b.py'],
                    'status': 'cohesive',
                    'naming_review': {'recommended_name': 'backend', 'reason': 'Stable backend family.'},
                }
            ],
            'migration_plan': {
                'summary': 'Move 12 files into 3 folders, keep 4 root facades, review 2 singleton files.',
                'folders_to_create': ['backend', 'analysis', 'reporting'],
                'file_moves': [{'from': 'a.py', 'to': 'src/architec/backend/a.py'}],
                'review_files': [{'path': 'io_utils.py'}],
            },
        },
    )
    monkeypatch.setattr(runner, 'build_component_graph', lambda snapshot: {'core': []})

    result = runner.run_analysis(tmp_path, goal='stabilize core', diff=True, base='main', head='HEAD')

    analysis_path = tmp_path / '.architec' / 'architec-analysis.json'
    summary_path = tmp_path / '.architec' / 'architec-summary.md'
    viz_path = tmp_path / '.architec' / 'architec-viz.html'
    assert analysis_path.exists()
    assert summary_path.exists()
    assert viz_path.exists()
    data = json.loads(analysis_path.read_text(encoding='utf-8'))
    assert data['meta']['mode'] == 'diff'
    assert data['scores']['structure'] > 0
    assert data['scores']['structure_dimensions']['package_topology'] > 0
    assert data['topology']['needs_folder_management'] is True
    assert len(data['topology']['migration_plan']['file_moves']) == 1
    assert data['artifacts']['summary_md'].endswith('architec-summary.md')
    assert result['summary']['headline'] == 'Snapshot'
