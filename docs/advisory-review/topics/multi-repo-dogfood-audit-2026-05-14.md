# Multi-Repo Dogfood Audit 2026-05-14

This note records a dogfood run of Architec against three small external Python
libraries:

- `pypa/packaging`
- `pallets/itsdangerous`
- `python-humanize/humanize`

It is an Architec self-assessment and product signal, not an audit request for
those projects. The repositories were cloned into `/tmp/architec-dogfood-*` so
generated `.hippocampus/` and `.architec/` data did not affect user workspaces.

## Commands

```bash
git clone --depth 1 https://github.com/pypa/packaging.git /tmp/architec-dogfood-packaging-2002792
git clone --depth 1 https://github.com/pallets/itsdangerous.git /tmp/architec-dogfood-itsdangerous-2002796
git clone --depth 1 https://github.com/python-humanize/humanize.git /tmp/architec-dogfood-humanize-2002797

PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full /tmp/architec-dogfood-packaging-2002792 --skip-auth --out /tmp/architec-dogfood-packaging-review.json
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full /tmp/architec-dogfood-itsdangerous-2002796 --skip-auth --out /tmp/architec-dogfood-itsdangerous-review.json
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full /tmp/architec-dogfood-humanize-2002797 --skip-auth --out /tmp/architec-dogfood-humanize-review.json
```

The full CLI path exposed two product-level dogfood issues before all three
reviews could complete:

- `packaging` and `itsdangerous` refreshed Hippo data successfully, then stopped at
  bundle validation because `file-manifest.json` included `docs/Makefile` and
  `docs/conf.py` while Architec's current source-tree check did not count those
  paths as architecture source.
- `humanize` reached full analysis, then stopped during backend LLM preflight /
  summary execution because the configured provider returned HTTP 403.

To continue evaluating the deterministic AI drift detectors, this run used the
scanner layer directly:

```bash
PYTHONPATH=/home/bfly/workspace/architec/src python3 - <<'PY'
from pathlib import Path
from architec.code_review.near_duplicate import near_duplicate_scan
from architec.code_review.shadow_implementation import (
    shadow_implementation_file_dry_run,
    shadow_implementation_scan,
)

for root in [
    Path("/tmp/architec-dogfood-packaging-2002792"),
    Path("/tmp/architec-dogfood-itsdangerous-2002796"),
    Path("/tmp/architec-dogfood-humanize-2002797"),
]:
    print(root)
    print("near", len(near_duplicate_scan(root, limit=20)["concerns"]))
    print("shadow", len(shadow_implementation_scan(root, limit=20)["concerns"]))
    print("file", shadow_implementation_file_dry_run(root, limit=10)["pair_total"])
PY
```

## Results

`itsdangerous`:

- `near_duplicate`: 0 concerns
- `shadow_implementation`: 0 concerns
- file-level dry-run: 0 candidate pairs

This is the desired behavior for a compact mature security library. The
detectors did not invent duplicate or shadow findings.

`humanize`:

- `near_duplicate`: 1 concern
- `shadow_implementation`: 0 concerns
- file-level dry-run: 0 candidate pairs

The single duplicate was `thousands_separator()` versus `decimal_separator()` in
`src/humanize/i18n.py`. This is a likely intentional paired accessor pattern:
both functions read the active locale and return a fallback separator, but they
serve different locale concepts.

`packaging`:

- `near_duplicate`: at least 20 reported concerns under the current limit
- `shadow_implementation`: 6 concerns
- file-level dry-run: 0 candidate pairs

Useful or plausible observations:

- `direct_url._get_object` versus `pylock._get_object` is a credible duplicate
  helper signal. Both retrieve a mapping value and convert it with
  `_from_dict`, differing mainly in domain-specific validation error type. A
  shared helper or explicit divergence note could be reasonable.

Weak or noisy observations:

- Benchmark functions under `benchmarks/` produced near-duplicate concerns.
  Benchmark suites often intentionally repeat timing shapes with different
  inputs. These should behave like test/support code for AI drift scanners. The
  benchmark exclusion part is now covered by
  [Decision 054](../decisions/054-ai-drift-mature-library-calibration.md).
- `Marker.__and__` versus `Marker.__or__` and `Version.post` versus
  `Version.dev` are intentional paired API variants. They share shape because
  the public API is symmetric, not because a new wheel was accidentally built.
- `humanize` showed the same broader pattern with
  `thousands_separator()` versus `decimal_separator()`. These explicit paired
  API variant cases are now covered by
  [Decision 054](../decisions/054-ai-drift-mature-library-calibration.md).
- `shadow_implementation` parser concerns in `packaging` matched
  `_parse_glibc_version`, `_parse_musl_version`, `_parse_local_version`, and
  `_parse_version_many`. These functions are all parsers, but they parse
  different domain grammars: libc runtime versions, local package versions, and
  requirement/version-token grammar. This parser-subdomain precision issue is
  now covered by
  [Decision 057](../decisions/057-shadow-parser-subdomain-taxonomy.md).

## Product Lessons

The multi-repo run complements the earlier Hippocampus and python-dotenv runs:

- Hippocampus exposed duplicate/shadow precision issues in a larger active
  codebase.
- python-dotenv exposed full-review display calibration for small mature
  libraries.
- This run exposed full CLI dogfood reliability issues and mature-library
  variant patterns in deterministic AI drift scanners.

The next Architec refinements should focus on:

1. **Offline/static dogfood path**: code-review should offer a reliable
   deterministic/static path when backend LLM configuration is unavailable, or
   at least degrade to a structured result instead of preventing dogfood. This
   is now covered by
   [Decision 058](../decisions/058-full-code-review-static-degradation.md).
2. **Hippo bundle source-scope alignment**: fresh Hippo bundles should not be
   marked stale because Hippo and Architec disagree about docs source files such
   as `docs/Makefile` and `docs/conf.py`.
3. **Benchmark/test-support exclusion and paired API variant suppression**:
   covered by
   [Decision 054](../decisions/054-ai-drift-mature-library-calibration.md).
   `benchmark` / `benchmarks` should be treated like tests/support for AI drift
   scanners, and `near_duplicate` should suppress narrow same-file paired API
   variants such as dunder operator pairs, post/dev accessors, and locale
   separator accessors.
4. **Parser domain taxonomy**: covered by
   [Decision 057](../decisions/057-shadow-parser-subdomain-taxonomy.md).
   `shadow_implementation` now distinguishes clear runtime/platform,
   local-version, and version-grammar parser subdomains before emitting primary
   concerns.
5. **Advisory recall lane**: because Architec recommendations are reviewed
   before any code changes land, plausible lower-confidence parser or module
   candidates should be observable in a discovery lane before they are promoted
   to primary concerns. This direction is recorded in
   [Decision 055](../decisions/055-advisory-recall-discovery-lane.md), and the
   first artifact/signal implementation is recorded in
   [Decision 056](../decisions/056-advisory-discovery-lane-v1.md).

These are Architec product-signal adjustments. They do not imply any of the
dogfood repositories should change their code.

## Follow-Up Run After Decisions 054/056/057/058

After the scanner calibration and static-degradation decisions landed, the same
temporary repositories were reviewed again with:

```bash
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full --skip-auth --out /tmp/architec-dogfood-<name>-review-after-058.json /tmp/architec-dogfood-<name>-*
```

Observed results:

- `packaging`: returned `analysis_mode=static` instead of stopping. It produced
  19 primary concerns and one `advisory_discovery` signal with two suppressed
  paired API candidates (`Marker.__and__` / `Marker.__or__`, `Version.post` /
  `Version.dev`).
- `itsdangerous`: returned `analysis_mode=static`, with zero primary concerns
  and no discovery candidates. This remains the desired behavior for a compact
  mature library.
- `humanize`: completed the normal full path, with 12 generated concerns, four
  displayed hotspot concerns, and one discovery candidate for the
  `decimal_separator` / `thousands_separator` paired accessor pattern.

This confirms that Decision 058 fixes the dogfood reliability problem: full
review now returns structured output even when the Hippo/LLM-backed path is
unavailable.

The same run exposed a new calibration question for mature libraries:
`packaging` still has several primary `near_duplicate` concerns that look like
intentional same-file API or class-family variants rather than accidental drift:

- `Version.major` / `Version.minor` / `Version.micro` tuple accessors;
- `PackageWheel` / `PackageSdist` same-member variants in `pylock.py`;
- `Specifier` / `SpecifierSet` / `BaseSpecifier` filter/repr variants;
- `_UpperBound.__eq__` / `_LowerBound.__eq__`.

These are not clear enough to delete from the product signal entirely, but they
are better represented as grouped primary observations or discovery candidates
than as repeated one-concern-per-member output. This is now covered by
[Decision 059](../decisions/059-near-duplicate-member-variant-families.md).

## Follow-Up Run After Decisions 059/060

After Decision 059 landed, the same three repositories were cloned again into
fresh `/tmp/architec-dogfood-*-after-059` directories and reviewed with:

```bash
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full --skip-auth --out /tmp/architec-dogfood-<name>-after-059-review.json /tmp/architec-dogfood-<name>-after-059
```

Initial results showed that LLM-backed analysis was available: `humanize`
completed the normal full path. `packaging` and `itsdangerous` still degraded to
static review, but their reason was not backend LLM availability. Both fresh
Hippo bundles were rejected because `file-manifest.json` marked docs-side files
such as `docs/conf.py` and `docs/Makefile` as source while Architec's local path
policy classified those paths as docs.

That source-scope mismatch is now covered by
[Decision 060](../decisions/060-hippo-manifest-source-scope-alignment.md). After
the validation fix, both repositories returned normal full review output:

- `packaging`: `analysis_mode` absent (normal full path), `overall=86.73`,
  `concern_total=39`, `top_concern_total=5`, with `near_duplicate`,
  `shadow_implementation`, and `advisory_discovery` signals still present.
- `itsdangerous`: normal full path, `overall=96.73`, `concern_total=14`,
  `top_concern_total=5`, with cleanup/archive/semantic judge/hotspot/topology
  context available.
- `humanize`: normal full path, `overall=97.77`, `concern_total=12`,
  `top_concern_total=4`, and one paired-accessor discovery candidate.

Decision 059 reduced the mature-library API-family noise from the earlier
`packaging` run: member families are grouped or discovery-only rather than
repeated as one primary concern per member. The same retest exposed a full-review
cleanup/archive display issue: `packaging` and `itsdangerous` could still show
changelog or docs-side stale-doc/archive observations in top concerns even when
the semantic cleanup judge marked those paths `keep_active`. This display
calibration is now covered by
[Decision 061](../decisions/061-semantic-keep-active-display-calibration.md):
semantic `keep_active` stale-doc conflicts are demoted from default top
concerns while raw cleanup/archive artifacts remain intact. A follow-up smoke
after Decision 061 confirmed the intended display shift: `packaging` no longer
showed `CHANGELOG.rst` / `docs/Makefile` stale-doc archive observations in the
top five, and `itsdangerous` no longer showed `CHANGES.rst` as a top concern
after the semantic judge marked it `keep_active`.

The same signal has a positive counterpart: when the semantic judge says a
cleanup/archive path still needs `review`, that explicit judgment should be
visible in the primary portfolio. Decision 062 adds
`semantic_judge.decision=review` evidence and a modest confidence floor for
matching cleanup/archive concerns, while leaving raw artifacts and fix-advice
unchanged.

The stronger semantic cleanup decisions are now handled by [Decision
064](../decisions/064-semantic-archive-retire-display-reinforcement.md):
`archive_first` and `retire_now` add factual semantic evidence and a stronger
display confidence floor to matching cleanup/archive concerns without creating
new concerns, changing artifact contracts, or changing the advisory boundary.

## Follow-Up Run After Decisions 061-064

After the semantic display calibration decisions landed, Architec was run
against fresh temporary clones under `/tmp/archi-dogfood/`:

```bash
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full --skip-auth --out /tmp/archi-dogfood/<name>-full.json /tmp/archi-dogfood/<name>
```

The LLM-backed full path was available for all three repositories:

- `itsdangerous`: normal full review, `overall=96.73`,
  `concern_total=14`, `top_concern_total=4`. Top concerns were one
  `fallback_branch` cleanup observation on `src/itsdangerous/serializer.py`
  with `semantic_judge.decision=review`, plus three hotspot observations. The
  `CHANGES.rst` stale-doc/archive context stayed out of displayed concerns
  after `keep_active` calibration.
- `humanize`: normal full review, `overall=97.77`, `concern_total=12`,
  `top_concern_total=4`. Top concerns were hotspot observations only. The
  `decimal_separator` / `thousands_separator` paired accessor appeared as one
  `advisory_discovery` candidate with `promoted_total=0`, not as a primary
  duplication concern.
- `python-dotenv`: normal full review, `overall=96.51`,
  `concern_total=14`, `top_concern_total=2`. Top concerns were hotspot
  observations on `src/dotenv/cli.py` and `src/dotenv/main.py`. The complete
  concerns artifact still retained `CHANGELOG.md` and `docs/changelog.md`
  cleanup/archive observations with `semantic_judge.decision=review`, but
  active-changelog display calibration kept them out of the default portfolio.

These results are broadly aligned with the intended product behavior:

- compact mature libraries do not produce duplicate/shadow primary noise;
- paired public API accessors remain discoverable without inflating
  `concerns[]`;
- semantic cleanup decisions are visible when they reinforce a displayed
  cleanup/archive concern, while `keep_active` and active-changelog calibration
  keep known low-value stale-doc contexts out of top concerns.

The same run surfaced one remaining display-quality follow-up in Architec's own
diff review: selected-scope cleanup and archive observations for the same path
could both occupy incremental top concern slots. Full review already deduped
cleanup/archive display by path and category, but diff/since selected scope
preserved both. This is now covered by [Decision
065](../decisions/065-incremental-cleanup-archive-display-dedupe.md): the
default incremental portfolio displays one representative cleanup/archive
observation per path/category while preserving the raw generated concerns
artifact.
