# Shadow Parser Subdomain Taxonomy

Date: 2026-05-15

## Context

The multi-repo dogfood run against `packaging` showed that the coarse
`parser` role can over-match mature version/protocol parsing code. Functions
such as `_parse_glibc_version`, `_parse_musl_version`, `_parse_local_version`,
and `_parse_version_many` all look parser-shaped, but they serve different
grammar domains.

The default `shadow_implementation` concern lane should stay high-precision,
while ambiguous parser candidates can still be inspected through dogfood and
the advisory discovery lane.

## Decision

Add a conservative parser subdomain split to `shadow_implementation`.

When both candidates share the coarse `parser` role, suppress clear
cross-subdomain pairs before concern construction:

- runtime / platform parser tokens such as `glibc`, `musl`, `libc`,
  `manylinux`, `musllinux`, `platform`, and `runtime`;
- local-version parser tokens such as `local`;
- version grammar parser tokens such as `requirement`, `specifier`, `marker`,
  `token`, `grammar`, or clearly generic version parser names.

Same-subdomain parser pairs remain eligible. Ambiguous or mixed-domain parser
candidates remain eligible rather than being suppressed. Existing parser-helper
signals such as JSON block parsing remain eligible.

This is a precision filter only. It does not change concern schema, thresholds,
`references[].role`, `concern_id`, diff/since scope, fix-advice behavior, or
module-level shadow public signal status.

## Non-Goals

This does not:

- infer parser domains from LLM or prose;
- suppress all version-related parser pairs;
- promote parser candidates into advisory discovery by itself;
- change `shadow_implementation` file/module dry-run behavior;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Mature protocol/version libraries are less likely to report unrelated parser
  subdomains as primary `shadow-implementation` concerns.
- Same-domain parser shadow signals remain reportable.
- Ambiguous parser cases remain available for future dogfood and discovery-lane
  calibration.
