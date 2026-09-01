# precheck-agent-workflow Specification

## Purpose
TBD - created by archiving change add-precheck-skill. Update Purpose after archive.
## Requirements
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

### Requirement: Compression is data-sensitive and diagnosis-led

The Skill SHALL guide the Agent to open a user-supplied filesystem path through
`mediasense.dataset.open`, hand the returned exact `dataset_ref` to PreCheck Run,
and run a suitable available initial configuration without asking the Human to
predict a correct Evidence count. It SHALL treat frontier size as an observation
to evaluate with distribution, coverage, local cost, downstream review burden,
and uncertainty.

#### Scenario: User supplies only a filesystem path

- **WHEN** a user asks to prepare a filesystem path and no `dataset_ref` is known
- **THEN** the Agent opens the path through `mediasense.dataset.open`, reports the selected portable or local workspace, and passes only the returned exact `dataset_ref` to `mediasense.precheck.run`

#### Scenario: Dataset opening is blocked

- **WHEN** Dataset opening reports corrupt, incompatible, ambiguous, unsafe, or unverifiable state
- **THEN** the Agent explains the exact workspace and recovery choices and does not bypass it by creating lower-priority state or scanning the source directly

#### Scenario: First preparation of a large Dataset

- **WHEN** the host supplies an exact `dataset_ref` and no prior Result exists for a large Dataset
- **THEN** the Agent starts an appropriate available initial configuration without inventing a universal or user-supplied Evidence-count target

#### Scenario: User questions a 500-entry frontier

- **WHEN** an initial Result contains 500 entry Evidence objects and the user questions whether its distribution is reasonable
- **THEN** the Agent inspects the exact Result, asks for the concrete quality problem, and does not classify the count alone as success or failure

#### Scenario: Diagnosis-led revisions produce 3 then 200 entries

- **WHEN** a supported profile revision made for the diagnosed problem produces 3 entries and the user reports over-compression before a second revision produces 200
- **THEN** the Agent treats 500, 3, and 200 as observed outputs of three distinct immutable Results, explains each qualitative trade-off, and relies on Tool-managed valid-work reuse rather than presenting the counts as requested targets

### Requirement: Agent reports cost as evidence becomes available
The Skill SHALL distinguish observed cost, defensible estimates, and unknowns
across local PreCheck work, optional external work, downstream model work, and
Human review attention.

#### Scenario: Local compression reaches an external checkpoint
- **WHEN** the Tool exposes a completed compression frontier and a pending reverse-geocode proposal
- **THEN** the Agent reports the available frontier and review burden, the exact pending logical-query count, and any remaining cost unknowns before asking for the online decision

#### Scenario: Immutable Result exposes actual effects
- **WHEN** the Result becomes readable
- **THEN** the Agent reports actual provider requests, retry or fallback effects, billable-call knowledge, and material downstream Evidence burden from the Result without substituting Source Item counts or estimates

#### Scenario: Evidence frontier is paginated
- **WHEN** an exact entry Evidence count is material and the Read response does not provide a total
- **THEN** the Agent completes the bounded traversal before reporting an exact count

### Requirement: PreCheck remains local-first with one bounded online exception
The Skill SHALL keep all external work disabled by default and SHALL recognize
only the confirmed contract for reverse geocoding a normalized, deduplicated
coordinate set frozen after compression.

#### Scenario: Default local run
- **WHEN** the user has not enabled the online exception
- **THEN** the Agent starts and describes the Run as local-first without authorizing remote models, online maps, uploads, or billable calls

#### Scenario: Frozen reverse-geocode set needs confirmation
- **WHEN** the Tool pauses with a frozen reverse-geocode proposal
- **THEN** the Agent presents the exact logical-query count, explains that coordinates leave the local boundary and may reveal visited places, distinguishes unknown provider handling or cost, and obtains a matching Human proceed or skip decision before requesting resume

#### Scenario: User skips reverse geocoding
- **WHEN** the Human declines the frozen reverse-geocode proposal
- **THEN** the Agent requests the Tool-supported skip path, explains that optional place evidence will be absent, and claims a durable qualification only when the immutable Result returns one

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
- **THEN** the Agent reports only the retained work and required capacity the Tool exposes, marks missing facts unknown, and resumes only after a reported verifiable condition is satisfied

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
- **THEN** the Agent inspects relevant existing Result-local Evidence, diagnoses the likely cause, and proposes only a supported configuration revision, directed rebuild, or an honest partial or blocked outcome instead of hiding uncertainty or inventing a Tool action

### Requirement: Result axes govern handoff and escalation
The Skill SHALL interpret coverage, readiness, and integrity independently and
SHALL hand Plan only an exact immutable Result reference whose limitations are
made explicit.

#### Scenario: Result is partial but plan-ready
- **WHEN** `mediasense.precheck.read` reports partial coverage, `plan_ready` readiness, and valid integrity
- **THEN** the Agent may offer the exact `result_ref` to Plan together with material qualifications and omissions

#### Scenario: Result is blocked
- **WHEN** `mediasense.precheck.read` reports blocked readiness
- **THEN** the Agent explains the blocking evidence and asks the Human to choose a successor Run, a supported directed rebuild or other evidence, or retaining the Result and stopping without claiming Plan readiness, resuming, or cancelling the completed Run

#### Scenario: Result is ready for Plan
- **WHEN** the Human proceeds with a valid plan-ready Result
- **THEN** the Agent hands Plan the exact `result_ref` and directs all later PreCheck fact and Evidence access through `mediasense.precheck.read`

### Requirement: PreCheck requires the current Honeycomb Tool Host

The PreCheck Skill SHALL require a compatible MediaSense Tool Host already loaded
in the current Honeycomb session. It SHALL route a missing or incompatible Host
to the `mediasense` product entry Skill rather than owning installation,
project-scoped MCP configuration, session restart, or whole-product readiness.

#### Scenario: PreCheck Tools are unavailable

- **WHEN** `mediasense.dataset.open`, `mediasense.precheck.run`, or `mediasense.precheck.read` is not discoverable in the current session
- **THEN** the Agent stops before Dataset work, explains the local integration prerequisite, and routes setup through the `mediasense` Skill before a new session retries discovery
