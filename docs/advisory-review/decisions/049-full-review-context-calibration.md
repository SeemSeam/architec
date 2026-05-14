# Full Review Context Calibration

Date: 2026-05-14

## Context

The python-dotenv dogfood run tested Architec against a small, mature Python
library. The result was broadly healthy: high score, no duplicate/shadow
implementation findings, and plausible hotspots on the main runtime and CLI
files.

The same run exposed full-review display calibration issues. Active changelogs
and release notes can look like stale docs when they contain words such as
deprecated or removed. Cleanup and archive signals can duplicate attention for
the same path. Topology can promote low-pressure boundary concerns even when
`needs_folder_management=false` and the package has a small flat file count.

These are context and display issues, not reasons to delete the underlying
detectors. The raw signals remain useful for full review, but top-level concerns
should not overstate low-value or duplicate observations.

## Decision

Add full-review context calibration v1 for displayed/top concerns only.

In v1:

- full review keeps running the existing cleanup, archive, semantic judge,
  hotspot, and topology signals;
- active changelog or release-note stale-doc concerns should be suppressed from
  top-level concerns or demoted when the file appears to be live release
  documentation, such as an active changelog, release notes file, or document
  with current/unreleased entries;
- cleanup and archive concerns for the same path should not both occupy
  top-level concerns; they should be merged, de-duplicated, or display-limited
  to one visible retention observation for that path;
- topology boundary concerns should remain signal context rather than top-level
  concerns when `needs_folder_management=false` and the flat file count is
  small;
- raw cleanup, archive, semantic judge, hotspot, and topology signals and
  generated artifacts remain available for consumers that need full context;
- the complete generated concerns artifact may still retain suppressed or
  demoted observations as context when useful, but the default `concerns[]`
  portfolio should be calibrated for user trust.

The intended behavior is narrow: improve full-review top concern trust for small
mature libraries without weakening the detectors or changing advisory-only
semantics.

## Non-Goals

This does not:

- delete cleanup, archive, semantic judge, hotspot, or topology detectors;
- change diff/since scope hygiene from Decision 041;
- change stale-doc inventory categories globally;
- claim all changelogs or release notes are active;
- suppress high-pressure topology findings when a project needs folder
  management;
- introduce schema-breaking changes;
- change `concern_id` semantics for displayed concerns;
- change review events, status, or fix-advice behavior;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Full review top concerns should be less noisy on small mature libraries.
- Active release documentation is less likely to appear as stale-doc debt in the
  default concern portfolio.
- Cleanup/archive same-path retention observations should not consume multiple
  top concern slots.
- Topology remains useful context without overstating low-pressure flat-package
  structure.
- Consumers that need raw context can still inspect signals and generated
  artifacts.
