# Architecture Stability Next Priorities

Date: 2026-05-14

## Context

The advisory-review migration and first AI-specific signals are complete. `code-review`, `plan-review`, `fix-advice`, and `status` now form a stable advisory loop. The remaining product question is whether `architec` can protect long-term architecture quality from vibe-coding drift, repeated implementation, and mainline instability.

Current capabilities can surface many structural concerns, but they do not guarantee correctness or enforce project-specific architectural contracts.

## Decision

Prioritize the next architecture-stability work in this order:

1. architecture contracts for ownership, allowed dependency direction, and public boundary expectations;
2. plan/diff consistency checks that compare reviewed plans with actual changed files and dependency edges;
3. test/churn risk fusion that combines existing test/coverage/churn signals with code-review concerns;
4. module/file-level shadow implementation only after dry-run false-positive controls and positive fixtures improve;
5. multi-language expansion after the Python signal model remains stable.

Keep all of these advisory-only. They should produce concerns, signals, evidence, and fix-advice options, not merge decisions.

The first phase should land architecture contracts before adding another generic detector. The intended first contract concern is `architecture-contract`, backed by explicit repository rules such as ownership, allowed dependency direction, facade usage, or public API boundary expectations.

The second phase should connect `plan-review` artifacts to `code-review --diff`, so coding-agent changes can be compared with declared plan touchpoints and boundary expectations.

The third phase should read external test, coverage, and churn reports as optional context. It should enrich concern risk context rather than execute tests or create a separate health verdict.

## Non-Goals

This does not:

- turn `architec` into a CI gate;
- promise behavioral correctness;
- execute tests or collect runtime telemetry directly;
- promote file-level shadow implementation to a public signal;
- add TypeScript or Go support in this step.

## Consequences

- The next phase focuses on preventing architecture drift rather than adding more smell detectors.
- Project-specific boundary contracts become the highest-leverage path toward long-term maintainability.
- Plan-review and code-review should become more connected, so coding-agent changes can be checked against declared intent.
- Test/churn fusion waits until it can consume existing project reports without owning test execution.
- File-level shadow implementation remains deferred until it has better scoping, fixtures, and taxonomy.

## Acceptance Signals

This direction is working when:

- a repository can express at least one dependency-direction or ownership contract in versioned config;
- `code-review --diff` can report a changed-file-scoped contract concern with rule evidence;
- a repository without contract config produces no contract signal and no contract concern;
- a saved plan-review result can be compared with the current diff without requiring a legacy goal flag;
- test/churn context can raise or annotate concern risk using external data, while preserving advisory-only output;
- empty results remain neutral observations rather than claims of architectural safety.
