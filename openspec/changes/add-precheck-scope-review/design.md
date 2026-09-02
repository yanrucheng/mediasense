## Context

`mediasense.precheck.run` currently discovers and accounts for the complete
source boundary, then immediately admits the configured producer graph. A
media-shaped object nested under a dot directory, cache, backup, index, or old
output therefore receives the same expensive treatment as intended source
media unless an existing deterministic scope rule already demotes it.

The existing domain model already assigns Scope Discovery, Scope Decision, and
Accounting Closure to PreCheck. Dataset Open intentionally does not read source
media, and PreCheck Run already owns durable execution, pause/resume, and Result
publication. The missing behavior is a review boundary inside that Tool, not a
new stage or Tool.

The Human has confirmed a deliberately thin responsibility split:

- the Tool reports a factual statistical tree and enforces an exact selection;
- the Agent interprets names, structure, and impact for the Human;
- the Skill carries the reusable review method; and
- the Human or an explicitly delegated caller owns consequential inclusion and
  exclusion choices.

## Goals / Non-Goals

**Goals:**

- expose a compact and expandable factual view of the discovered source tree;
- stop before expensive Work until the scope is selected;
- let a caller express the whole selection as a default disposition plus
  source-relative subtree exceptions;
- retain excluded objects in normal PreCheck accounting;
- bind, persist, reuse, and invalidate selections honestly; and
- keep discovery bounded and usable for large trees.

**Non-Goals:**

- classify a path as a cache, backup, historical output, or legitimate media;
- maintain a directory-name blacklist or make hiddenness an exclusion rule;
- add a public Preflight Tool, Dataset Open scan, policy service, or new Agent;
- estimate wall-clock time, money, Evidence count, or semantic value from file
  counts; or
- repeat the completed PreCheck performance investigation or use the Hong Kong
  fixture as an implementation proof.

## Backward Compatibility Policy

| Attribute | Value |
|-----------|-------|
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumers exist. The current contract and private schema change
directly; version routers, dual writes, deprecation shims, and compatibility
adapters are prohibited.

## Decisions

### 1. Scope review is an admission checkpoint in the existing PreCheck Tool

After accounting discovery finishes, the coordinator projects a source
inventory and pauses before the first producer that performs metadata
extraction, full-content proof, decoding, rendition, video probing, embedding,
sensitivity analysis, compression, or online work. `start`, `status`, `resume`,
`pause`, and `cancel` remain the only public actions.

The public state remains `paused` with reason `scope_confirmation_required`.
The activity phase identifies `scope_review`. A separate Preflight Tool was
rejected because it would duplicate lifecycle and create a stale interval
between preflight completion and Run execution. Dataset Open was rejected
because source enumeration contradicts its identity-only contract.

### 2. The inventory contains facts, not semantic candidates

The inventory is derived from the Run's existing discovered items and issues.
It reports:

- an opaque inventory fingerprint and scan generation;
- complete-tree file count and byte total, with explicit unknown sizes;
- per-node descendant file count and byte total;
- deterministic file-kind counts and additive size buckets;
- a bounded number of lexicographically stable representative relative paths;
- discovery issue counts and incomplete subtrees; and
- a bounded pretty-tree projection with omitted child counts.

Names such as `.similarity_cache`, `.DS_Store`, `.agents`, or `old-output` are
ordinary observed relative paths. The Tool does not attach `cache`, `derived`,
`backup`, confidence, recommendation, or materiality labels.

Size buckets are preferred over percentile calculation because they are
streamable, additive, deterministic, and useful without retaining all sizes in
memory. The initial boundaries are implementation-owned presentation details,
not domain semantics.

### 3. One status action supports bounded tree navigation

Normal `status` includes the root inventory projection when scope selection is
pending. An optional source-relative `scope_path` asks the same action to return
that subtree, and `scope_after` continues through an oversized sibling list.
Each response has fixed depth, child, and representative budgets; collapsed
nodes report how many immediate children were omitted.

This avoids both an unbounded response and a sixth public Run action. The
selection is independent of what happened to be visible in one page.

### 4. Selection is a default plus disjoint subtree exceptions

A scope decision submitted through `resume` contains:

- `kind: "source_scope"`;
- the exact inventory fingerprint;
- `default_disposition: "include" | "exclude"`; and
- zero or more source-relative subtree exceptions, each taking the opposite
  disposition from the default.

The common choice is default include with explicit exclusions. Default exclude
with explicit inclusions supports intentionally narrow Runs. Exception paths
must name nodes present in the inventory, remain within the source root, and be
pairwise non-overlapping. Rejecting overlaps keeps meaning obvious without
introducing rule precedence.

Included discoveries continue through existing kind and auxiliary
classification. Excluded discoveries receive scope `excluded`, retain their
condition, and append a scope-selection basis referencing the inventory and
selection digests. A selection does not authorize remote work or alter any
other PreCheck control.

### 5. Selection identity and reuse are content-bound

The inventory fingerprint is computed over the complete ordered factual
inventory needed to apply the selection: relative path, kind, size presence and
value, relevant file identity/change observations, discovery issues, and scan
completion. The digest algorithm is private and replaceable; the public
guarantee is that a materially different inventory cannot satisfy an old
selection.

Before admitting expensive Work after `resume`, the coordinator performs a new
discovery generation. If its inventory fingerprint differs, the submitted
selection remains recorded as an attempted decision but is not applied; the Run
pauses on the new inventory. Existing source verification still handles byte
changes after admission and before Result publication.

A later Run over the same Dataset may reuse the latest completed selection only
when the new inventory fingerprint matches exactly. Reuse creates a new Run
projection that cites the earlier decision; it does not mutate the earlier Run
or Result. The first implementation deliberately does not generalize a choice
to future descendants.

### 6. Persistence stays in existing Working Run and Result authority

Private Working Run storage retains the inventory fingerprint, inventory
summary, pending selection, accepted selection, and reused-decision reference.
No public Scope Review artifact is introduced. The immutable Result continues
to be the cross-stage authority: every discovered item is accounted for and an
excluded item carries the scope-selection basis.

The Agent must not infer state from the private store. All pending inventory,
accepted-transition, stale-selection, and terminal facts are exposed through
`mediasense.precheck.run`.

### 7. The Agent and Skill own interpretation

The PreCheck Skill instructs the Agent to inspect the statistical tree, expand
relevant subtrees, explain only evidence actually returned by the Tool, and
distinguish its interpretation from Tool facts. Hiddenness alone is never
presented as proof that media should be excluded.

The Agent proposes an include/exclude partition and obtains Human direction
when the choice is not already delegated. It then submits the exact selection.
The Tool validates and executes it but does not claim that the selection is
semantically correct.

### 8. Unattended behavior fails closed at the same boundary

A first Run with no reusable selection pauses after inventory. An unattended
caller receives the same machine-readable status and may submit an exact
selection programmatically. If it does nothing, no expensive Work is admitted.
There is no hidden `include everything` or `ignore hidden content` mode.

## Risks / Trade-offs

- **[A second discovery generation adds local I/O before expensive work]** →
  Keep both passes streaming and metadata-only, benchmark the scope-review path,
  and retain the correctness-first revalidation until an equally strong
  filesystem change mechanism is demonstrated.
- **[A bounded tree can hide a deeply nested surprising subtree]** → Every
  collapsed node retains aggregate counts and supports deterministic expansion;
  discovery issues and unknown sizes are never removed by truncation.
- **[Path-based choices can be invalid after rename or normalization changes]**
  → Bind them to the complete inventory fingerprint and validate normalized,
  source-relative paths before application.
- **[Always pausing the first Run adds one interaction]** → Reuse an exact prior
  selection on unchanged inventories and allow automated callers to submit the
  same explicit decision shape; do not trade away the admission guarantee.
- **[Aggregating every ancestor can amplify work on very deep paths]** → Enforce
  the existing path/depth safety bounds and build summaries in one bounded
  streaming pass over persisted run items.
- **[The active scale-precheck-execution change touches orchestration]** → Keep
  this change before producer demand and preserve all scale work after scope is
  accepted; run its focused suite without reopening its completed analysis.

## Migration Plan

1. Add and validate the OpenSpec deltas and public contract examples.
2. Extend private Working Run state and factual inventory projection.
3. Gate orchestration after accounting and apply exact selections to Run items.
4. Update the PreCheck Skill and packaged copies.
5. Add focused synthetic contract, lifecycle, orchestration, and scale tests.
6. Replace the pre-production contract in place; existing incompatible Dataset
   workspaces are not migrated under the repository's Zero BC policy.

Rollback consists of reverting the change before release. No source media is
mutated and no compatibility state is retained.

## Open Questions

None. The Human has selected factual Tool output plus Agent interpretation over
Tool-owned semantic candidate classification.
