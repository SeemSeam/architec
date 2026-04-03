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

    @staticmethod
    def component_for_path(path: str) -> str:
        return 'core' if 'core' in path else 'misc'


def test_run_analysis_writes_architec_artifacts(tmp_path, monkeypatch):
    (tmp_path / 'src' / 'legacy').mkdir(parents=True)
    (tmp_path / 'src' / 'legacy' / 'core.py').write_text(
        "def legacy_core():\n    return 'legacy implementation'\n",
        encoding='utf-8',
    )
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'legacy-core.md').write_text(
        'Deprecated old flow for core module\n',
        encoding='utf-8',
    )
    (tmp_path / '.architecture-rules.toml').write_text(
        "\n".join(
            [
                "[[archi.cleanup_metadata]]",
                'path = "docs/legacy-core.md"',
                'owner = "docs-team"',
                "ttl_days = 14",
                'expires_at = "2099-01-01"',
                "",
                "[[archi.cleanup_metadata]]",
                'path = "src/legacy/core.py"',
                'owner = "core-team"',
                'expires_at = "2000-01-01"',
                "",
            ]
        )
        + "\n",
        encoding='utf-8',
    )
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
    monkeypatch.setattr(
        runner,
        'suggest_feature_architecture',
        lambda *args, **kwargs: {
            'target_components': [{'component': 'core', 'score': 18.0, 'evidence_paths': ['src/core/service.py']}],
            'candidate_files': [{'path': 'src/core/service.py', 'component': 'core', 'score': 14}],
        },
    )
    monkeypatch.setattr(
        runner,
        'score_changed_components',
        lambda *args, **kwargs: {
            'incremental_score': {'score': 91.0},
            'changed_file_total': 1,
            'components': [
                {
                    'component': 'core',
                    'changed_files': ['src/compat/core_adapter.py'],
                    'changed_file_count': 1,
                }
            ],
        },
    )
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
    monkeypatch.setattr(
        runner,
        '_run_semantic_judge',
        lambda *args, **kwargs: {
            'status': 'ok',
            'candidate_pool_total': 2,
            'reviewed_total': 2,
            'by_decision': {'archive_first': 1, 'retire_now': 1},
            'summary': 'Judged top cleanup candidates.',
            'top_judgments': [
                {
                    'path': 'docs/legacy-core.md',
                    'decision': 'archive_first',
                    'confidence': 0.91,
                    'reason': 'stale doc',
                }
            ],
            'judgments': [
                {
                    'path': 'docs/legacy-core.md',
                    'decision': 'archive_first',
                    'confidence': 0.91,
                    'reason': 'stale doc',
                },
                {
                    'path': 'src/legacy/core.py',
                    'decision': 'retire_now',
                    'confidence': 0.88,
                    'reason': 'legacy implementation with replacement',
                    'replacement': 'src/core.py',
                },
            ],
        },
    )

    result = runner.run_analysis(tmp_path, goal='stabilize core', diff=True, base='main', head='HEAD')

    analysis_path = tmp_path / '.architec' / 'architec-analysis.json'
    cleanup_inventory_path = tmp_path / '.architec' / 'architec-cleanup-inventory.json'
    cleanup_ledger_path = tmp_path / '.architec' / 'architec-cleanup-ledger.json'
    cleanup_summary_path = tmp_path / '.architec' / 'architec-cleanup-summary.md'
    archive_candidates_path = tmp_path / '.architec' / 'architec-archive-candidates.json'
    archive_summary_path = tmp_path / '.architec' / 'architec-archive-summary.md'
    semantic_judge_path = tmp_path / '.architec' / 'architec-semantic-judge.json'
    semantic_judge_summary_path = tmp_path / '.architec' / 'architec-semantic-judge-summary.md'
    summary_path = tmp_path / '.architec' / 'architec-summary.md'
    viz_path = tmp_path / '.architec' / 'architec-viz.html'
    assert analysis_path.exists()
    assert cleanup_inventory_path.exists()
    assert cleanup_ledger_path.exists()
    assert cleanup_summary_path.exists()
    assert archive_candidates_path.exists()
    assert archive_summary_path.exists()
    assert semantic_judge_path.exists()
    assert semantic_judge_summary_path.exists()
    assert summary_path.exists()
    assert viz_path.exists()
    data = json.loads(analysis_path.read_text(encoding='utf-8'))
    assert data['meta']['mode'] == 'diff'
    assert data['scores']['structure'] > 0
    assert data['scores']['structure_dimensions']['package_topology'] > 0
    assert data['topology']['needs_folder_management'] is True
    assert len(data['topology']['migration_plan']['file_moves']) == 1
    assert data['cleanup']['candidate_total'] >= 1
    assert data['cleanup']['owner_total'] == 2
    assert data['cleanup']['ttl_total'] == 1
    assert data['cleanup']['expires_total'] == 2
    assert data['cleanup']['expired_total'] == 1
    assert data['archive_candidates']['candidate_total'] >= 1
    assert data['archive_candidates']['top_candidates'][0]['owner'] == 'docs-team'
    assert data['semantic_judge']['status'] == 'ok'
    assert data['feature_analysis']['retire_plan']['add'][0]['component'] == 'core'
    assert data['feature_analysis']['retire_plan']['retire']
    assert data['change_analysis']['retire_plan']['add'][0]['signals'] == ['compat']
    assert data['change_analysis']['retire_plan']['retire']
    assert data['artifacts']['summary_md'].endswith('architec-summary.md')
    assert data['artifacts']['cleanup_inventory_json'].endswith('architec-cleanup-inventory.json')
    assert data['artifacts']['archive_candidates_json'].endswith('architec-archive-candidates.json')
    assert data['artifacts']['semantic_judge_json'].endswith('architec-semantic-judge.json')
    assert result['summary']['headline'] == 'Snapshot'
