> 第6包持续视图的拟议产品承诺；当前公开合约尚未更新。HTTP实现选择见本包design.md，不是永远固定的产品方法。

## ADDED Requirements

### Requirement: A current-state page is delivered throughout Plan
The existing Tool surface SHALL provide a current Work page beginning at create, including absent organization, notes-only state, partial draft, complete candidate, withdrawal and successful seal. Agent-authored HTML, layout, image mosaics or a second presentation business dataset SHALL NOT be prerequisites. Tool replies SHALL expose usable current and exact-revision entry points or a truthful delivery failure.

#### Scenario: Discussion begins before directories exist
- **WHEN** a plan-ready Result is bound to a new Work
- **THEN** the page exposes saved context and the absence of organization without waiting for a complete candidate

#### Scenario: Discussion changes a saved plan
- **WHEN** a new planning revision is committed
- **THEN** opening or refreshing the current entry yields that revision or a later current revision, or explicitly reports unavailable delivery; an older view is not labelled current

### Requirement: Entry lifetime has an actual owner
The runtime SHALL own the lifetime, access boundary and recovery of the delivered local page. The entry SHALL remain usable after the producing Tool call completes. A compatible ordinary Dataset reconnection and inspect SHALL reacquire an entry after process restart without Agent-generated business data. Transient serving addresses SHALL NOT be represented as permanent Plan identities, and a dead short-lived process SHALL NOT be reported as an available entry.

#### Scenario: CLI invocation ends
- **WHEN** the create or update CLI process exits after reporting a ready view
- **THEN** the reported page remains served by its actual runtime owner

#### Scenario: View Host stopped
- **WHEN** the Host has stopped and an ordinary inspect requests view delivery
- **THEN** the runtime restores and verifies a compatible entry or explicitly reports unavailable, without changing Work revision

### Requirement: Current-state presentation preserves distinct meanings
The page SHALL distinguish Result coverage, chosen Plan scope, assigned and unassigned members, organization kind, evidence/delivery limitations, and actual final confirmation. Working notes and preferences SHALL be visibly separate from the final content carried by Candidate decision_notes. Local feedback, free text and full accounting SHALL NOT create confirmation badges. Actual confirmed/frozen status SHALL come from the existing successful seal record.

#### Scenario: All draft items have outcomes
- **WHEN** a saved draft covers its whole scope
- **THEN** the page still labels it draft and does not report Human confirmation or a sealable candidate

#### Scenario: Context is known but organization is absent
- **WHEN** notes describe possible groups but no structured organization is saved
- **THEN** those notes remain process text, not inferred directories or member assignments

### Requirement: Missing evidence and unavailable core views differ
Individual image failures SHALL preserve usable organization, counts and explanations with explicit placeholders and provenance. An untrusted Result or unresolved membership SHALL prevent claims of current complete validation. Neither case SHALL silently change organization or acquire replacement evidence. View recovery SHALL preserve the saved version.

#### Scenario: A selected image cannot be read
- **WHEN** a valid Result-local Evidence reference has an unavailable local rendition
- **THEN** the page reports a degraded view and identifies that image limitation without substituting an unrelated source

#### Scenario: The Result cannot be trusted
- **WHEN** required Result integrity or membership resolution fails
- **THEN** the core view is unavailable for complete review and seal remains subject to the existing trusted-Result rejection

### Requirement: History boundaries and withdrawal are explicit
The first delivery SHALL NOT imply permanent historical-draft retention, comparison or restoration. Obsolete entries SHALL be marked superseded; any retained snapshot SHALL be marked historical. Clearing organization SHALL remove it from the current view and remove its sealable identity. A closed Work SHALL remain tied to its own Frozen Plan rather than silently following a later Work.

#### Scenario: Old cache is gone
- **WHEN** an old exact-revision page is requested after its cache has been discarded
- **THEN** the runtime reports its unavailability/obsolescence and does not manufacture it from current content

## MODIFIED Requirements

### Requirement: Preview is bound to exact candidate content
Each displayed view SHALL bind one Work, exact revision and Result, plus the global candidate identity when a complete candidate exists. Directories, notes, counts, member pages and evidence references SHALL use that same snapshot. Current entry and exact-revision entry SHALL be distinguishable. Already displayed content SHALL NOT silently switch to another candidate while the Human is reviewing it.

#### Scenario: Open an exact revision
- **WHEN** a reviewer follows the revision-specific URI for the current revision
- **THEN** the displayed data is bound to that revision and reports its actual organization kind and identity availability

#### Scenario: Open an obsolete revision
- **WHEN** the Work has been updated or withdrawn after that revision
- **THEN** a new access reports superseded and offers the current entry rather than serving current data under the old identity

#### Scenario: Seal closes an unchanged revision
- **WHEN** the reviewed candidate is successfully sealed
- **THEN** the page can show its actual frozen record under the same organization revision without treating closure as a new planning edit

### Requirement: Preview exposes the complete review structure
The page SHALL expose the saved directory hierarchy, exact expanded member counts, explicit other outcomes, unassigned scope where applicable, material decision_notes, applicable members, qualified supporting Evidence and bounded deterministic samples. File names and necessary provenance SHALL be readable by a Human; opaque Source Item references SHALL NOT be the only member display. No application-specific investigation panel SHALL become mandatory product structure.

#### Scenario: Review a saved directory
- **WHEN** a directory has assigned members and prepared images
- **THEN** it shows correct counts and traceable samples, with source provenance distinguished from represented membership

#### Scenario: An explanation applies to selected items
- **WHEN** decision_notes name an exact Source Set and Result-local Evidence
- **THEN** the reviewer can read the explanation, expand its affected members and access the actual Evidence or its stated delivery limitation

#### Scenario: Damaged and unresolved items differ
- **WHEN** scoped items include damaged assigned media, readable unresolved media, unassigned items and explicit retention outcomes
- **THEN** these meanings and their scopes remain distinguishable rather than one undifferentiated exception count

### Requirement: Preview supports bounded drill-down
The delivered page SHALL provide functional bounded browsing of directories, members, other outcomes, unassigned items, notes and their evidence. Continuations SHALL preserve Work revision, target collection and query semantics and SHALL reach the real end without silent truncation or duplication. Changing revision SHALL invalidate incompatible continuation. A default page size SHALL NOT become a claim that only that many members exist.

#### Scenario: Browse beyond the first one hundred members
- **WHEN** a directory contains more than one page
- **THEN** actual browser controls retrieve additional names and details from the same revision until complete, rather than displaying an instruction with no working action

#### Scenario: A byte-limited Evidence page continues
- **WHEN** a response ends early because of a byte budget or an individual item fails
- **THEN** the remaining continuation is preserved and unread Evidence is not reported as already inspected

### Requirement: Preview is deterministic and non-authoritative
Equivalent Work snapshots, Result content and rendering profile SHALL yield equivalent logical tree, counts, ordering, explanations and sample selection. Live delivery availability and observation time SHALL remain distinguishable from saved planning content. Views, indexes and caches SHALL be regenerable under the owning Plan workspace and SHALL NOT replace Work, Result or Frozen Plan authority.

#### Scenario: Rebuild after cache loss
- **WHEN** derived view caches are deleted while authorities remain available
- **THEN** the current view is rebuilt without new organization decisions, revision changes or confirmation

#### Scenario: Older rendering finishes late
- **WHEN** a render for an obsolete revision completes after a newer state exists
- **THEN** publication checks prevent it from replacing the current entry or reversing its version

### Requirement: Preview performs no semantic or external side effects
The renderer SHALL read only existing planning authorities and bounded Result-local evidence through owned boundaries. It SHALL NOT modify source media or Result, invent groups or names, follow arbitrary paths from prose, acquire Geo/model evidence or perform external hosting. Local serving and derived storage SHALL have an explicit runtime owner and effect scope. Saved text SHALL be rendered as data, not executable page code.

#### Scenario: Zero external acquisition
- **WHEN** a page is delivered with local prepared evidence
- **THEN** no external provider, CDN, model or media upload is required

#### Scenario: Text contains HTML or a local path
- **WHEN** a saved explanation includes markup, a script or an arbitrary path
- **THEN** it remains safely displayed text and grants no execution, file access or attachment custody

### Requirement: Preview presentation is validated by a Human reference review
Implementation acceptance SHALL include Human review of a representative page produced through the actual installed ordinary Tool entry. Automated schema, renderer or internal Python checks SHALL NOT be treated as acceptance of comprehensibility, navigation, missing-evidence visibility or exact-version review. This requirement SHALL NOT force Agent-authored production HTML during specification work.

#### Scenario: First installed continuous page is available
- **WHEN** the ordinary Tool entry delivers the representative empty, draft and candidate views
- **THEN** Human review assesses their navigation and meaning before the page implementation is accepted
