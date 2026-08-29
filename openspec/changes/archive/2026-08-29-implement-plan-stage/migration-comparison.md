# Plan Migration Comparison

This comparison covers the implemented Mock-driven Plan capability. It does not claim that unfinished PreCheck production evidence producers or Apply are complete.

| Capability | Judgment | Evidence and operating-quality effect |
| --- | --- | --- |
| Date/location/content candidate use | `intentionally_changed` | Plan consumes Result-local candidates and Evidence but the Agent and Human own final organization; fixed legacy thresholds no longer become final truth. |
| Representative visual review | `preserved` | Preview reuses available representative renditions, shows counts and bounded drill-down, and reports missing visuals rather than hiding directories. |
| Per-representative captioning | `intentionally_changed` | The Skill uses progressive, decision-relevant visual attention instead of requiring remote captions for nearly every representative; actual model and egress cost must be reported. |
| Visual location inference | `intentionally_changed` | Place claims remain challengeable Plan evidence; reverse geocoding remains an optional upstream evidence producer rather than a repeated Plan effect. |
| Per-item title and modal cluster naming | `intentionally_changed` | The Agent names the whole sibling organization coherently and the Human reviews exact paths in preview. |
| Direct output-tree construction | `intentionally_changed` | Candidate revision, deterministic validation, preview, exact Human confirmation, and immutable seal precede any Apply effect. |
| Draft/cache reuse | `preserved` | SQLite persists the complete validated candidate, opaque revision, preferences, idempotency, and recovery state; ordinary inspect performs zero PreCheck rereads. |
| User correction | `intentionally_changed` | Preview feedback creates a new revision only for coherent semantic changes; old previews cannot confirm new content. |
| Source-file safety | `preserved` | Plan performs no source mutation, and the Frozen Plan is not Apply authorization. |
| Failure and uncertainty visibility | `intentionally_changed` | Missing evidence, invalid candidates, stale revisions, identity mismatch, unavailable confirmation, publication conflict, and recovery state remain distinguishable. |

No implemented Plan capability is currently classified as a known `regression`. Real-fixture end-to-end acceptance remains separate until the necessary production PreCheck Evidence is available.
