## ADDED Requirements

### Requirement: PreCheck reduces demand before expensive media work
The orchestrator SHALL account every Source Item and produce the configured index
metadata needed for grouping before demanding detailed metadata, visual
renditions, video frames, embeddings, or sensitivity observations. Initial
expensive media Work SHALL be limited to deterministic representatives, useful
boundaries, and explicit exceptions while Result coverage continues to account
for every Source Item.

#### Scenario: Large Dataset reaches a bounded visual demand set
- **WHEN** index metadata groups many eligible Source Items into fewer bundle candidates
- **THEN** the Run demands initial visual and optional model Work only for the configured representative, boundary, and exception set rather than every bundle member

#### Scenario: An unrendered member remains covered
- **WHEN** an accounted Source Item is outside the bounded initial visual frontier
- **THEN** Result navigation retains that Source Item directly without fabricating per-item visual Evidence or claiming a public bundle relationship that the Result does not contain

#### Scenario: Directed evidence remains internal
- **WHEN** a caller uses the public `mediasense.precheck.run` start or successor request
- **THEN** no directed-evidence selector is accepted or advertised until a separate public contract defines authorization, Result binding, and failure semantics

### Requirement: Batched provider execution preserves item semantics
The orchestrator SHALL permit one bounded provider operation to execute multiple
ready item Work records while retaining one semantic Work identity, lease,
outcome, provenance record, and invalidation boundary per item. Batch scheduling
state and provider process identity MUST NOT become durable product authority.

#### Scenario: Metadata batch succeeds
- **WHEN** one ExifTool lane returns trustworthy rows for multiple leased Source Items
- **THEN** each item commits its own success or explicit missing observations with the shared provider version and its exact subject and sidecar dependencies

#### Scenario: One input breaks a metadata batch
- **WHEN** a provider batch fails without trustworthy per-item attribution
- **THEN** execution subdivides the batch within configured bounds until successful siblings commit and each failing item receives its own outcome

#### Scenario: Cancellation arrives between batches
- **WHEN** a Run is paused or cancelled after one batch commits
- **THEN** no new batch begins, committed item Work remains reusable, and uncommitted leases recover through existing Work semantics

#### Scenario: Metadata heartbeat cannot renew its leases
- **WHEN** the batch heartbeat fails while item Work leases are still active
- **THEN** execution stops that heartbeat, transitions every still-owned active item to retryable failure immediately, preserves already committed siblings, and surfaces the renewal failure without waiting for natural lease expiry

### Requirement: Effective resources are resolved and frozen per Run
PreCheck SHALL resolve execution capacities from operator ceilings, enabled
producers, and observable host and source/workspace characteristics. The
effective numeric capacities, provider batch bounds, and external codec thread
allowance SHALL be persisted in the existing Run configuration before expensive
Work begins. Network capacity SHALL remain zero unless separately authorized.

#### Scenario: Unknown or remote source storage
- **WHEN** storage locality cannot support a stronger concurrency judgment
- **THEN** the resolved profile starts with a conservative source-heavy lane count while allowing independent workspace and CPU work within their ceilings

#### Scenario: Verified local solid-state source admits independent work
- **WHEN** a supported storage probe identifies a physical solid-state source and CPU and memory observations support more than one independent lane
- **THEN** the resolved profile may run compatible resource claims concurrently without exceeding persisted CPU, memory, process, codec, model, or I/O ceilings

#### Scenario: Run resumes on the same configuration
- **WHEN** an interrupted Run resumes
- **THEN** it reuses the persisted effective resource configuration instead of silently resolving different method limits

### Requirement: Scale-critical execution is bounded
The supported PreCheck path SHALL enumerate Source Items and Work demand through
bounded pages, batches, or queues and MUST NOT rescan all Run items once per
media subject. Grouping outside an explicitly bounded group SHALL use algorithms
with `O(N log N)` or better growth, and content representative selection SHALL
enforce a finite comparison budget.

#### Scenario: One million generated Source Items
- **WHEN** generated accounting and index metadata contain one million Source Items without real media decoding
- **THEN** metadata-to-bundle planning, initial evidence selection, and queued calls use production iterators and keep non-authoritative coordination memory bounded by configured pages, groups, evidence limits, and pending windows rather than total item count
- **AND** the immutable canonical Result payload is reported separately as necessary `O(N)` authority rather than being misreported as bounded coordination state

#### Scenario: Filename sidecars are resolved
- **WHEN** metadata demand needs sidecars for many subjects
- **THEN** execution uses the indexed Run association rather than loading and scanning every Run item for each subject

#### Scenario: Compression group exceeds the exact comparison bound
- **WHEN** a content-bearing group is larger than the configured exact-comparison budget
- **THEN** representative selection uses a bounded replaceable method and records its method limitations instead of performing unbounded all-pairs comparison
