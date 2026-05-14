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
- File-level shadow implementation remains deferred until it has better scoping, fixtures, and taxonomy.
