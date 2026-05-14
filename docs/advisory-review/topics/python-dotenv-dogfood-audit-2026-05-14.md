# python-dotenv Dogfood Audit 2026-05-14

This note records a dogfood run of Architec against a small external Python
library, `theskumar/python-dotenv`. It is an Architec self-assessment and product
signal, not an audit request for python-dotenv.

The repository was cloned into `/tmp/archi-dogfood-python-dotenv` and analyzed
there so generated `.hippocampus/` and `.architec/` data did not affect any user
workspace.

## Command

```bash
git clone --depth 1 https://github.com/theskumar/python-dotenv.git /tmp/archi-dogfood-python-dotenv
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full /tmp/archi-dogfood-python-dotenv --out /tmp/python-dotenv-archi-full-20260514.json --skip-auth
```

## Result

The full review reported:

- overall score `96.65`;
- `summary.concern_total=14`;
- `top_concern_total=5`;
- signal kinds: cleanup, archive, semantic_judge, hotspot, topology.

No `near_duplicate` or `shadow_implementation` concerns were emitted. That is a
good sign for a small mature library: the AI/vibe-coding drift detectors did not
invent duplicate or shadow findings where there were none.

## Reasonableness Assessment

Useful or reasonable observations:

- `src/dotenv/main.py` and `src/dotenv/cli.py` as hotspots are plausible. In a
  small package, these are naturally the main behavior and CLI surfaces.
- The high overall score matches the visible structure: a compact package with
  clear source root, limited module count, and no duplicate/shadow implementation
  findings.

Weak or noisy observations:

- `CHANGELOG.md` and `docs/changelog.md` were flagged as stale-doc cleanup and
  archive candidates because the changelog contains words such as deprecated or
  removed. In this repository, the changelog is active release documentation,
  including an `Unreleased` section and recent version entries. This is a
  cleanup/archive false positive pattern.
- The same changelog path can appear as both cleanup and archive top concerns.
  That duplicates attention for one underlying retention question.
- Topology emitted boundary concerns for files under `src/dotenv` even though
  `topology.needs_folder_management=False` and `flat_file_total=8`. For a small
  single-package library, a flat module layout can be intentionally healthy. The
  concern is low value unless the project is growing or a changed file is adding
  responsibilities.
- Semantic judge reviewed the cleanup candidates and returned `keep_active` for
  both, but top concerns still showed cleanup/archive candidates. The display
  layer should account for semantic disagreement before promoting cleanup/archive
  to top concerns.

## Product Lessons

The python-dotenv run complements the Hippocampus dogfood run:

- Hippocampus exposed duplicate/shadow precision issues.
- python-dotenv exposes full-review context calibration issues in mature small
  libraries.

The next Architec refinements should focus on:

1. **Cleanup/archive display calibration**: merge or de-duplicate cleanup and
   archive concerns for the same path, and account for semantic judge
   `keep_active` before top concern promotion.
2. **Changelog/release-note stale-doc suppression**: do not treat active
   changelogs, release notes, or docs with current/unreleased entries as stale
   just because they contain words such as deprecated or removed.
3. **Topology boundary calibration for small flat packages**: when
   `needs_folder_management=False` and `flat_file_total` is low, keep topology
   as signal context rather than top-level boundary concerns.

These are product-signal adjustments for Architec. They do not imply
python-dotenv should change its repository structure.
