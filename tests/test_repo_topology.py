from __future__ import annotations

from pathlib import Path

from architec.analysis.repo_topology import review_folder_topology


class _Snapshot:
    def __init__(self, root: Path):
        self.project_root = root
        self.metrics = {'findings': []}
        self.index = {
            'files': {
                'src/architec/backend_llm/config.py': {},
                'src/architec/backend_llm/flow.py': {},
                'src/architec/backend_llm/gateway.py': {},
                'src/architec/feature_advisor.py': {},
                'src/architec/feature_query.py': {},
                'src/architec/component_scoring.py': {},
                'src/architec/component_graph.py': {},
                'src/architec/orchestrator.py': {},
                'src/architec/orchestrator_batches.py': {},
                'src/architec/report_markdown.py': {},
                'src/architec/viz_generator.py': {},
                'src/architec/io_utils.py': {},
                'src/architec/llm_guard.py': {},
            }
        }
        self.signatures = {
            'files': {
                'src/architec/backend_llm/config.py': {
                    'signatures': [{'name': 'TieredLLMConfig'}]
                },
                'src/architec/component_scoring.py': {
                    'signatures': [{'name': 'score_changed_components'}]
                },
                'src/architec/report_markdown.py': {
                    'signatures': [{'name': 'render_summary_markdown'}]
                },
            }
        }

    def first_party_paths(self):
        return list(self.index['files'].keys())

    def first_party_findings(self):
        return []

    def signatures_for_file(self, path: str):
        return self.signatures.get('files', {}).get(path, {}).get('signatures', [])


def test_review_folder_topology_reports_flat_root(tmp_path, monkeypatch):
    snapshot = _Snapshot(tmp_path)
    monkeypatch.setattr(
        'architec.analysis.repo_topology.load_or_build_component_descriptors',
        lambda *args, **kwargs: {
            'architec:backend_llm': {
                'files': [
                    'src/architec/backend_llm/config.py',
                    'src/architec/backend_llm/flow.py',
                    'src/architec/backend_llm/gateway.py',
                ],
                'descriptor_terms': ['backend', 'llm', 'gateway'],
                'responsibility_summary': 'Backend LLM runtime and gateway.',
            },
            'architec:scoring': {
                'files': [
                    'src/architec/component_scoring.py',
                    'src/architec/component_graph.py',
                ],
                'descriptor_terms': ['scoring', 'components', 'graph'],
                'responsibility_summary': 'Component scoring and graph logic.',
            },
        },
    )

    review = review_folder_topology(tmp_path, snapshot=snapshot, llm_enabled=False)

    assert review['source_root'] == 'src/architec'
    assert review['flat_file_total'] == 10
    assert review['needs_folder_management'] is False
    assert {item['group_id'] for item in review['groups']} == {'feature', 'orchestrator'}
    assert any(
        item['group_id'] == 'orchestrator'
        and item['programmatic_name'] == 'orchestrator'
        for item in review['groups']
    )
    assert 'orchestrator' in review['migration_plan']['folders_to_create']
    assert any(
        item['to'] == 'src/architec/orchestrator/orchestrator_batches.py'
        for item in review['migration_plan']['file_moves']
    )
    assert any(
        item['path'] == 'src/architec/io_utils.py'
        for item in review['root_placement_review']['misplaced_root_files']
    )
    assert any(item['kind'] == 'root_non_facade_file' for item in review['findings'])


def test_review_folder_topology_applies_llm_group_and_file_adjudication(tmp_path, monkeypatch):
    snapshot = _Snapshot(tmp_path)
    monkeypatch.setattr(
        'architec.analysis.repo_topology.load_or_build_component_descriptors',
        lambda *args, **kwargs: {
            'architec:orchestrator': {
                'files': [
                    'src/architec/orchestrator.py',
                    'src/architec/orchestrator_batches.py',
                ],
                'descriptor_terms': ['orchestrator', 'batches'],
                'responsibility_summary': 'Orchestration flow and batching.',
            },
        },
    )
    monkeypatch.setattr(
        'architec.analysis.repo_topology.run_cached_analysis',
        lambda *args, **kwargs: (
            {
                'group_reviews': [
                    {
                        'group_id': 'orchestrator',
                        'decision': 'accept',
                        'recommended_folder': 'runtime',
                        'alternatives': ['orchestrator'],
                        'reason': 'Runtime folder is acceptable for orchestration flows.',
                        'confidence': 0.82,
                    }
                ],
                'file_reviews': [
                    {
                        'path': 'src/architec/io_utils.py',
                        'decision': 'move',
                        'keep_root': False,
                        'recommended_folder': 'support',
                        'alternatives': ['integration'],
                        'reason': 'Utility implementation should not stay at the root.',
                        'confidence': 0.77,
                    }
                ],
                'summary': 'Use backend and move io_utils into support.',
            },
            False,
        ),
    )

    review = review_folder_topology(tmp_path, snapshot=snapshot, llm_enabled=True)

    orchestrator_group = next(
        item for item in review['groups'] if item['group_id'] == 'orchestrator'
    )
    assert orchestrator_group['topology_review']['recommended_folder'] == 'runtime'
    assert any(item['folder'] == 'runtime' for item in review['migration_plan']['folder_plans'])
    assert any(
        item['to'] == 'src/architec/support/io_utils.py'
        for item in review['migration_plan']['file_moves']
    )


def test_review_folder_topology_skips_true_compat_wrappers_only(tmp_path, monkeypatch):
    source_root = tmp_path / 'src/architec'
    source_root.mkdir(parents=True)
    (source_root / 'compat_demo.py').write_text(
        "from ._compat_reexport import reexport\n\nreexport(__package__ or 'architec', '.support.io_utils', globals())\n",
        encoding='utf-8',
    )
    (source_root / 'repo_topology.py').write_text(
        "from ._compat_reexport import reexport\n\n"
        "def not_a_wrapper():\n"
        "    reexport(__package__ or 'architec', '.support.io_utils', globals())\n",
        encoding='utf-8',
    )
    snapshot = _Snapshot(tmp_path)
    snapshot.index['files'].update(
        {
            'src/architec/compat_demo.py': {},
            'src/architec/repo_topology.py': {},
        }
    )
    monkeypatch.setattr(
        'architec.analysis.repo_topology.load_or_build_component_descriptors',
        lambda *args, **kwargs: {},
    )

    review = review_folder_topology(tmp_path, snapshot=snapshot, llm_enabled=False)

    assert review['compat_wrapper_total'] == 1
    assert review['compat_wrappers'] == ['src/architec/compat_demo.py']
