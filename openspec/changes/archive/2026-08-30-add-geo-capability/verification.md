# Geo Capability Verification

## Automated verification

| Check | Result |
| --- | --- |
| `openspec validate add-geo-capability --strict --no-interactive` | pass |
| `ruff check src tests` | pass |
| Full non-live Pytest suite | pass |
| `git diff --check` | pass |

The suite exercises no live provider credentials or network calls. A live-provider
smoke remains an optional, separately authorized environment check.

## Reusable-capability acceptance

| Test | Result | Evidence |
| --- | --- | --- |
| Purpose | pass | PreCheck batch observation and Plan question-specific enrichment use the same coordinate-to-place capability without sharing stage policy. |
| Independent identity | pass | Removing the family loses effect guarding, normalized provider evidence, request-scoped routing, and replay safety rather than only code deduplication. |
| Replacement | pass | AMap, Google Maps, and fake adapters implement the provider-neutral operation port; callers do not consume provider-native responses. |
| Authority | pass | Missing or stale authorization, forbidden fields, provider limits, request ceilings, billing uncertainty, retention, and continuation changes are rejected before the additional effect. |
| Progression | pass | `resolve_place` is the default and returns a bounded `nearby_places` continuation; direct reverse and nearby operations remain available. |
| Evidence | pass | Candidate status, per-component outcome, attempts, datum, fallback, actual requests, billable units or unknown, and qualifications remain visible. |
| Isolation | pass | The family imports no PreCheck, Plan, or Apply module. Plan validates coordinates through PreCheck Read and stores observations only in Plan Working State. |
| Credentials | pass | Adapter secrets are absent from request identity, results, journal entries, Plan observations, and tests. |
| Failure | pass | Refused, unavailable, failed, partial, cancelled, and indeterminate paths remain distinguishable. |
| Consumer | pass | Existing PreCheck uses the family batch port; `mediasense.plan.work` `enrich_geo` exercises the public Geo boundary end to end. |

## Stage invariants

- PreCheck still freezes and deduplicates coordinates after compression, pauses for
  exact Human confirmation, owns Work reuse and routing continuity, and projects
  immutable candidate Evidence.
- Plan accepts only coordinates observable through the exact bound PreCheck Result,
  stores Geo output as Plan-owned candidate evidence, advances the revision when
  evidence is retained, and keeps observation, Agent judgment, and Human
  confirmation distinct.
- Preview reads stored Geo evidence and performs zero provider requests.
- Apply has no Geo dependency and performs no new semantic decision.

## Provider and lifecycle checks

- AMap retains its one-request combined legacy path for PreCheck and exposes
  address-only and nearby-only operation-aware paths for the family.
- Google Maps retains legacy reverse-plus-nearby behavior and exposes each component
  independently for progressive calls.
- Route context is explicit and request-scoped; overlapping calls do not share
  provider/language mutation.
- The Tool journal admits an effect before provider access, returns the same
  terminal result on identical replay, rejects conflicting request IDs, and keeps
  an interrupted effect indeterminate without automatic retry.
- No shared observation cache, provider registry, Geo Artifact, service, or Geo
  Skill was introduced.

## Migration judgment

See `migration-comparison.md`. No known legacy Geo capability regressed. Provider
and datum behavior is preserved; authorization, failure semantics, accounting,
state isolation, and Plan-local enrichment are intentionally changed. Live
provider accuracy, quota behavior, and routing quality remain environment-specific
and require separate authorization to measure.
