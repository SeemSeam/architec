# Architecture Contract Fix Advice

Date: 2026-05-14

## Context

Decision 036 added `architecture-contract` concerns for changed-file-scoped restricted imports. Those concerns include rule id, source glob, imported module, restricted import, optional owner, and optional human guidance in `next_steps_hint`.

Without a dedicated `fix-advice` branch, these concerns fall back to generic advice even though they carry enough structured evidence for more useful boundary-oriented options.

## Decision

Add a dedicated `fix-advice` branch for `kind: "architecture-contract"`:

- consume factual evidence keys such as `architecture_contract.rule_id`, `architecture_contract.import`, `architecture_contract.restricted_import`, and `architecture_contract.owner`;
- use `next_steps_hint` as optional review context;
- suggest comparing the changed import with the matched contract;
- suggest routing through the intended boundary or facade when the contract should remain in place;
- suggest updating the contract record or related plan when the direct dependency is intentional.

The advice remains advisory-only. It does not decide whether the contract or changed import is correct.

## Non-Goals

This does not:

- generate patches or edits;
- add an automatic apply mode;
- change `architecture-contract` detection;
- change `.architecture-rules.toml` shape;
- change plan/diff consistency;
- make contract concerns block review or CI.

## Consequences

- Contract concerns now produce more actionable boundary-oriented options in `fix-advice`.
- Teams can keep `rule.note` as human guidance without mixing it into factual evidence.
- Deeper contract-specific repair planning, such as generating facade extraction steps, remains future work.
