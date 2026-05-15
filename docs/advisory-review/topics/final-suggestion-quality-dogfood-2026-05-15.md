# Final Suggestion Quality Dogfood

Date: 2026-05-15

This is an Architec self-assessment and product-signal record. It is not an
audit request for the external repositories and does not imply those
repositories should change their code.

## Repositories

The final pass used the current local `architec` code against three small,
mature Python repositories already cloned under `/tmp/archi-dogfood`:

- `itsdangerous`
- `humanize`
- `python-dotenv`

Commands used:

```bash
PYTHONPATH=/home/bfly/workspace/architec/src \
  python3 -m architec code-review --full --skip-auth \
  --out /tmp/archi-dogfood-final/<repo>-full.json \
  /tmp/archi-dogfood/<repo>
```

All three runs completed through the normal LLM-backed full path, not the
static fallback path.

## Results

| Repository | Score | Top Concerns | Signal Quality |
| --- | ---: | ---: | --- |
| `itsdangerous` | 96.73 | 4 | Useful but cautious: `serializer.py` fallback branch was surfaced with semantic `review`; hotspot files were plausible review targets. |
| `humanize` | 97.77 | 4 | Good: no primary duplicate/shadow noise; paired API duplicate (`thousands_separator` / `decimal_separator`) stayed in discovery lane. |
| `python-dotenv` | 96.51 | 2 | Good: active changelog stale-doc observations stayed out of top concerns; top concerns focused on `main.py` and `cli.py` hotspot pressure. |

## Quality Assessment

The `CodeReviewResult.concerns[]` display now looks suitably conservative for
small mature libraries:

- no duplicate or shadow implementation observations polluted the top concerns
  in `humanize` or `python-dotenv`;
- paired API variants remain visible in discovery artifacts without becoming
  primary concerns;
- active changelog/release-note stale-doc observations remain available in raw
  artifacts but do not dominate top concerns;
- low-pressure topology observations remain raw context and do not occupy
  top-level display slots.

The output is still advisory, not a proof of repository health. High scores and
low concern counts mean Architec found limited architecture pressure under its
current heuristics.

## Remaining Product Observation

The human-readable `.architec/architec-summary.md` recommendations are generated
from the broader analysis report and can still mention low-pressure topology
review items even when `code-review` has demoted those topology observations
from top-level `concerns[]`.

This is not a CodeReviewResult correctness issue: the JSON review surface is
already calibrated. It is a follow-up polish item for suggestion quality:
human-facing summary recommendations should eventually reuse, or at least align
with, the same display calibration policy used by `code-review`.

## Conclusion

The current advisory-review implementation is suitable for close-out. Further
work should be treated as product polish and empirical calibration rather than
release-blocking architecture-review work.
