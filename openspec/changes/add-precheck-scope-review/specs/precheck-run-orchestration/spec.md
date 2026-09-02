## MODIFIED Requirements

### Requirement: A configured Run drives the complete PreCheck chain
The `mediasense.precheck.run` implementation SHALL durably prepare and
immediately return a source-bound configured Run. An internal host worker SHALL
then coordinate discovery/accounting, factual scope inventory and exact scope
selection, required Work, Artifact production, Evidence assembly, validation,
and automatic immutable Result publication without requiring the caller to
invoke individual producers or seal manually. The worker MUST NOT admit
expensive producer Work until the current inventory has an accepted or exactly
reusable scope selection.

#### Scenario: Small mixed Dataset
- **WHEN** a configured Run starts for supported image, video, and auxiliary inputs without a reusable scope selection
- **THEN** `start` immediately returns its `run_ref`, the host worker completes discovery and pauses with a factual scope inventory, and the producer graph proceeds only after an exact selection is accepted

#### Scenario: Unchanged successor Dataset scope
- **WHEN** a configured successor Run discovers the exact inventory covered by a reusable prior selection
- **THEN** the host worker records the reuse and proceeds through the required local producer graph without another scope pause

## ADDED Requirements

### Requirement: Scope review uses the existing Run lifecycle
Scope review SHALL remain inside `mediasense.precheck.run`. The public Tool SHALL
retain exactly `start`, `status`, `pause`, `resume`, and `cancel`; a pending scope
selection SHALL use `paused`, the reason `scope_confirmation_required`, and the
activity phase `scope_review`.

#### Scenario: Agent reads a collapsed subtree
- **WHEN** the Agent requests `status` with a valid source-relative scope path while scope review is pending
- **THEN** the same Run status returns a bounded factual projection rooted at that path without adding another public action

#### Scenario: Scope decision is accepted
- **WHEN** `resume` receives a valid source-scope decision for the current inventory
- **THEN** the Tool accepts the target-state transition and only a later status proves whether revalidation succeeded and expensive execution began

#### Scenario: Existing reverse-geocode confirmation occurs later
- **WHEN** an accepted scope permits a Run to reach the optional frozen reverse-geocode batch
- **THEN** its existing proceed-or-skip confirmation remains separately typed and cannot reuse or widen the source-scope decision

