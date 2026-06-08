# LLMGateway Config Preflight Hard Fail

Date: 2026-06-04

## Context

Incremental review is now the default `archi` path and depends on a configured
llmgateway strong model. Previous static-degradation behavior could turn a
missing or incomplete backend LLM configuration into a deterministic static
CodeReviewResult. That made it too easy to miss the real setup problem and read
the output as if LLM review had run.

## Decision

Treat backend LLM configuration preflight failures as input errors.

When `preflight_backend_llm` cannot find a configured candidate, API key, base
URL, or required tier/model mapping, the CLI should return the existing error
path instead of emitting static review JSON:

- return exit code `2`;
- print the preflight message to stderr;
- include the llmgateway configuration hint;
- do not run full, incremental, or static code-review fallback commands.

This supersedes the config-preflight portion of Decisions 058 and 066. Runtime
LLM unavailability after preflight may still use the existing marked static
degradation paths where those paths already apply.

## Consequences

Users get a direct setup reminder when llmgateway is not configured instead of a
degraded review result. Normal static degradation remains available for the
separate case where prerequisites passed but the review path later cannot use
the backend LLM.

## Non-Goals

- Add or display new cost telemetry.
- Remove runtime static degradation.
- Change Hippo bundle static degradation.
- Change llmgateway config file locations or schema.
