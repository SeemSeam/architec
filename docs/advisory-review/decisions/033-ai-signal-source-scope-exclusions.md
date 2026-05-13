# AI Signal Source Scope Exclusions

Date: 2026-05-14

## Context

File-level `shadow_implementation` dry-run sampling showed that repository-root scans can be dominated by local generated state. The first sample surfaced `.ccb/agents/.../provider-state/...` copies. After excluding `.ccb`, the next sanity sample surfaced `release-flow-test/runs/...` installed copies.

The same path-scope issue affects public AI signal scanners too: `near_duplicate` and function/class `shadow_implementation` scan Python files directly and maintain their own skip sets.

## Decision

Code-review AI signal scanners should default to project source, not generated state, local agent state, dependency copies, test fixtures, or cache directories.

The `near_duplicate` and `shadow_implementation` scanners exclude common non-source directories by relative project path, including:

- `.ccb`, `.architec`, `.hippocampus`, `.git`;
- Python and tooling caches;
- virtual environments and package caches;
- `node_modules`, `vendor`, generated assets, fixtures, test directories;
- local release/install test artifacts such as `release-flow-test` and `local-test-env`.

This is source scoping and noise control. It does not change detector thresholds, scoring formulas, concern kinds, ranking, payload guard, artifacts, or fix-advice behavior.

## Non-Goals

This does not:

- promote file-level `shadow_implementation` to CodeReviewResult;
- add module-level public concerns;
- change function/class shadow implementation semantics;
- change near-duplicate fingerprinting semantics;
- introduce source-root configuration.

## Consequences

- Public AI signal output is less likely to include local CCB/provider-state or generated install artifacts.
- Scanner skip behavior now better matches the existing path policy used elsewhere in the project.
- File-level `shadow_implementation` public signal remains deferred; remaining prerequisites are real positive fixtures and provider/plugin variant taxonomy, not `.ccb` exclusion.
