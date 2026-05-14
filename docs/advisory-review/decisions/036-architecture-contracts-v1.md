# Architecture Contracts V1

Date: 2026-05-14

## Context

The next architecture-stability gap is repository-specific boundary intent. Existing hotspot, topology, duplication, and shadow-implementation signals can show drift pressure, but they cannot know which imports or ownership boundaries are intentionally disallowed for a given project.

The repository already has `.architecture-rules.toml` for shared and `archi`-specific rules, so the first implementation should extend that file instead of adding a parallel config system.

## Decision

Add a conservative architecture contract v1:

- Read `[[shared.architecture_contracts]]` and `[[archi.architecture_contracts]]` from `.architecture-rules.toml`.
- Support changed-file-scoped dependency restrictions with:
  - `id` or `rule_id`;
  - `source_glob`;
  - `restricted_imports` or compatibility alias `forbidden_imports`;
  - optional `owner`;
  - optional `note`.
- Run contract checks only for `code-review --diff` and `code-review --since <ref>`.
- Only inspect changed Python files listed by `change_analysis.changed_files`.
- Emit `kind: "architecture-contract"` concerns when a changed file imports a restricted module.
- Emit an `architecture_contract` signal when contract rules are configured, including rule count, checked file count, and concern count.
- No contract config means no contract signal and no contract concern.

The output remains advisory-only. It reports the matched rule id, source glob, changed source path, imported module, restricted import, and optional owner as evidence; it does not decide whether the change is allowed to merge.

## Non-Goals

This does not:

- implement plan/diff consistency;
- read test, coverage, or churn reports;
- execute tests;
- add fix-advice special handling for `architecture-contract`;
- add TypeScript, Go, or non-Python import parsing;
- run contract checks in full review;
- introduce default contracts when no repository config exists.

## Consequences

- Projects can begin encoding explicit boundary intent in versioned config.
- `code-review --diff` and `--since` can report changed-file-scoped architecture contract concerns without surfacing historical violations.
- The first implementation is intentionally small and can be extended with facade expectations, ownership metadata, or plan/diff consistency later.
