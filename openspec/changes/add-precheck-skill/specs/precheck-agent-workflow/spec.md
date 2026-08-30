## ADDED Requirements

### Requirement: Skill activates only for the PreCheck stage
The `mediasense-precheck` Skill SHALL be normally discoverable for preparing,
observing, recovering, recompressing, and reading a MediaSense PreCheck Result,
and SHALL exclude Plan-owned organization decisions and Apply-owned filesystem
execution.

#### Scenario: User prepares a large Dataset
- **WHEN** a user asks to prepare a large media Dataset for later organization
- **THEN** the Skill activates and guides the PreCheck workflow

#### Scenario: User is naming groups in Plan
- **WHEN** a user asks to revise grouping or names in an existing Plan
- **THEN** the Skill does not take over that Plan-stage request

#### Scenario: User is executing Apply effects
- **WHEN** a user asks to execute, recover, or rewind filesystem effects for a Frozen Plan
- **THEN** the Skill does not take over that Apply-stage request

### Requirement: Skill preserves authority and Tool boundaries
The Skill SHALL guide Agent/Human interaction without owning source I/O,
Working Run state, confirmation truth, immutable Result truth, or direct access
to PreCheck persistence and SHALL route those responsibilities through the
formal `mediasense.precheck.run` and `mediasense.precheck.read` contracts.

#### Scenario: Agent starts and observes work
- **WHEN** the Agent begins preparation and follows a long-running Run
- **THEN** it uses `mediasense.precheck.run` for the start, status, and supported control transitions and distinguishes command acceptance from completed work

#### Scenario: Agent reads a published Result
- **WHEN** the Agent needs Result facts or additional Result-local Evidence
- **THEN** it uses `mediasense.precheck.read` with the exact immutable `result_ref` rather than reading a database, cache, or artifact layout

### Requirement: Compression remains goal-driven and revisable
The Skill SHALL guide the Agent to select compression according to the intended
downstream decision, review burden, coverage, local cost, and uncertainty while
leaving algorithms, implementations, thresholds, and fixed profiles open.

#### Scenario: First preparation of a large Dataset
- **WHEN** no prior Result exists for a large Dataset
- **THEN** the Agent establishes the decision purpose and explains an appropriate initial compression goal before starting the configured Tool workflow

#### Scenario: User changes a 500-item evidence target twice
- **WHEN** the user rejects 500 Evidence entries, requests 3, and later requests 200
- **THEN** the Agent treats each accepted target as a distinct Run and Result lineage, explains the changed review/coverage trade-off, and relies on Tool-managed valid-work reuse

### Requirement: PreCheck remains local-first with one bounded online exception
The Skill SHALL keep all external work disabled by default and SHALL recognize
only the confirmed contract for reverse geocoding a normalized, deduplicated
coordinate set frozen after compression.

#### Scenario: Default local run
- **WHEN** the user has not enabled the online exception
- **THEN** the Agent starts and describes the Run as local-first without authorizing remote models, online maps, uploads, or billable calls

#### Scenario: Frozen reverse-geocode set needs confirmation
- **WHEN** the Tool pauses with a frozen reverse-geocode proposal
- **THEN** the Agent presents the exact logical-query count and bounded coordinate-only scope and obtains a matching Human proceed or skip decision before requesting resume

#### Scenario: User skips reverse geocoding
- **WHEN** the Human declines the frozen reverse-geocode proposal
- **THEN** the Agent requests the Tool-supported skip path and retains the missing optional evidence as an explicit limitation

### Requirement: Agent explains observable recovery without inventing state
The Skill SHALL make Run status, progress, structured reasons, recovery
conditions, and allowed actions the basis for recovery guidance.

#### Scenario: Process is interrupted
- **WHEN** status reports a durable interrupted or paused Run
- **THEN** the Agent explains retained completed work and resumes only through an allowed Tool transition

#### Scenario: Source volume disconnects
- **WHEN** status reports the source volume unavailable
- **THEN** the Agent does not report files as deleted and waits for the Tool-reported compatible recovery condition before resume

#### Scenario: Workspace lacks capacity
- **WHEN** status reports insufficient workspace capacity
- **THEN** the Agent explains that committed work is retained and resumes only after the reported capacity condition is satisfied

#### Scenario: One media item is corrupt
- **WHEN** the Tool localizes one corrupt item while unrelated work can continue
- **THEN** the Agent preserves the item-level error and does not describe the whole Run as failed solely because of that item

### Requirement: Accounting and Evidence remain distinguishable
The Skill SHALL require every accounted Source Item to remain reachable through
the normal Evidence frontier or an explicit auxiliary, excluded, unsupported,
invalid, error, or unresolved path without requiring visual Evidence for every
Source Item.

#### Scenario: Accounted exceptional items lack visual renditions
- **WHEN** a Result accounts for exceptional or auxiliary Source Items without visual Evidence
- **THEN** the Agent treats their explicit paths and qualifications as valid accounting rather than silently omitting them or requiring invented renditions

#### Scenario: Evidence is insufficient for a downstream decision
- **WHEN** available Evidence cannot support the intended decision
- **THEN** the Agent proposes relevant Result-local expansion, recompression, directed rebuild, or an honest partial or blocked outcome instead of hiding the uncertainty

### Requirement: Result axes govern handoff and escalation
The Skill SHALL interpret coverage, readiness, and integrity independently and
SHALL hand Plan only an exact immutable Result reference whose limitations are
made explicit.

#### Scenario: Result is partial but plan-ready
- **WHEN** `mediasense.precheck.read` reports partial coverage, `plan_ready` readiness, and valid integrity
- **THEN** the Agent may offer the exact `result_ref` to Plan together with material qualifications and omissions

#### Scenario: Result is blocked
- **WHEN** `mediasense.precheck.read` reports blocked readiness
- **THEN** the Agent explains the blocking evidence and asks the Human to choose continued preparation, directed rebuild or other evidence, or stopping without claiming Plan readiness

#### Scenario: Result is ready for Plan
- **WHEN** the Human proceeds with a valid plan-ready Result
- **THEN** the Agent hands Plan the exact `result_ref` and directs all later PreCheck fact and Evidence access through `mediasense.precheck.read`
