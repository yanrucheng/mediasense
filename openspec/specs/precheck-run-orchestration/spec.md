# precheck-run-orchestration Specification

## Purpose
TBD - created by archiving change complete-precheck-run-orchestration. Update Purpose after archive.
## Requirements
### Requirement: A configured Run drives the complete PreCheck chain
The PreCheck Tool SHALL durably create a source-bound Run, acquire and launch its execution owner before returning run_ref, and coordinate discovery, scope confirmation, configured producers, validation and immutable publication internally. Start replay with identical request_id and effective input SHALL return the same Run without new execution; conflicting input SHALL fail.

#### Scenario: Small mixed Dataset
- **WHEN** a configured Run starts for images, video and auxiliary inputs
- **THEN** start returns run_ref promptly, internal work continues and completed status references the published Result

#### Scenario: Lost start response
- **WHEN** the caller repeats the same request_id and input
- **THEN** the original Run is returned even if it has since paused or completed, without launching a duplicate

#### Scenario: Startup failure
- **WHEN** no execution owner can be launched
- **THEN** start reports failure rather than an ownerless running success

### Requirement: Execution is configuration- and dependency-driven
The orchestrator SHALL run only capabilities selected by a durable Run
configuration and SHALL derive ordering from producer dependencies. It MUST NOT
materialize every optional producer merely because one implementation exists.

#### Scenario: Local minimal profile
- **WHEN** embeddings, sensitivity, and external geocoding are disabled
- **THEN** the Run omits them, performs zero network calls, and still completes when its selected evidence is sufficient

#### Scenario: Optional local evidence enabled
- **WHEN** an embedding or sensitivity profile and its local backend are enabled
- **THEN** the producer runs only after its required visual Artifact is available

### Requirement: Existing durability mechanisms govern recovery
The orchestrator SHALL use existing Work semantic identity, direct dependencies,
leases, attempts, Artifact publication, persisted Run configuration, and bounded
resource admission. Restart SHALL re-derive remaining demand and reuse valid
committed outputs.

#### Scenario: Process interruption between stages
- **WHEN** execution stops after a durable stage boundary
- **THEN** a resumed Run reuses completed Work and continues without manually reconstructing producer calls

#### Scenario: Cross-Run reuse
- **WHEN** another Run requests equivalent valid low-level work
- **THEN** it reuses the same Work and Artifact while publishing a distinct Result

### Requirement: Control and failure are honored during execution
The orchestrator SHALL durably accept pause/resume/cancel and return the observed state. It SHALL stop new work after pause/cancel admission, preserve successful siblings after localized failures, and expose actual external blocking conditions separately from unexpected execution failures. It SHALL NOT use blocked or paused to hide an invariant violation. Successful resume SHALL have a live execution owner.

#### Scenario: One corrupt image
- **WHEN** one image fails decoding and another succeeds
- **THEN** the success is retained and the failure has an explicit Source Item exception route

#### Scenario: Pause and resume
- **WHEN** a caller requests pause then later resumes the same Run
- **THEN** acceptance is distinct from achieving paused, no new work starts while paused, and remaining work reuses the same durable identity

#### Scenario: Cancel
- **WHEN** cancel is accepted before Result publication
- **THEN** no new work or Result is admitted, and already-attempted effects are not claimed to be undone

#### Scenario: Completion wins a race
- **WHEN** a control arrives after Result publication
- **THEN** current terminal state is retained and the control does not retract the Result

### Requirement: Completion is gated by closure and immutable publication
The orchestrator SHALL publish only after accounting, navigation, configured work, source verification and integrity gates pass. A terminal location no_result or known failed acquisition SHALL be accounted locally and SHALL NOT alone block publication or Plan readiness. Pending confirmations, in-flight work, invariant violations and indeterminate effects SHALL NOT be treated as completed business failures. Publication SHALL remain idempotent across crashes.

#### Scenario: Seal succeeds
- **WHEN** selected prerequisites close, including locally recorded missing location
- **THEN** Run status becomes completed and returns Result ref, coverage, readiness and material qualifications

#### Scenario: Seal crash window
- **WHEN** execution stops between Result registration and Run completion
- **THEN** recovery adopts the same verified Result and never publishes a duplicate

#### Scenario: All photos lack locations
- **WHEN** all otherwise usable photos have no GPS or terminal location failure
- **THEN** their Result can be complete and plan_ready without external reacquisition

### Requirement: Repeated compression creates independent Results
Distinct declared compression targets SHALL produce independent immutable
Results while reusing semantically valid lower-level Work and Artifact bytes.

#### Scenario: 500 to 3 to 200
- **WHEN** three Runs process the same unchanged 500-item Dataset with targets 500, 3, and 200
- **THEN** their entry counts match those targets, Result references are distinct, and low-level Work and Artifact production is not repeated



### Requirement: Status progress reports one honest counting domain
Status SHALL expose a single progress object with phase, unit, processed, total and last_progress_at. processed SHALL count terminal logical outcomes including reuse and finalized localized failure once, not retry attempts. Unknowns SHALL be null. Source accounting and detailed Work classifications SHALL be available through bounded include views rather than a false overall progress bar.

#### Scenario: Retry is still pending
- **WHEN** a transient Geo attempt failed but Tool retry remains scheduled
- **THEN** processed does not increase until the logical query reaches a terminal outcome

#### Scenario: Counting domain changes
- **WHEN** the phase or selected work membership changes
- **THEN** progress switches to that domain and same-phase membership change reports progress_scope_changed rather than a misleading continuous percentage

#### Scenario: Worker liveness becomes stale
- **WHEN** last durable progress is old and the execution owner's heartbeat expired
- **THEN** status explicitly reports suspected_stalled and allowed recovery controls without reclaiming the worker


### Requirement: Status details remain bounded and recoverable
Status SHALL provide accounting, diagnostics and confirmation include views over retained Run facts. Diagnostic pagination SHALL bind its content digest and reject changed snapshots. Default issue summaries SHALL signal truncation and provide full grouped diagnostics; status SHALL perform no new execution effects.

#### Scenario: Many localized issue classes
- **WHEN** more than five issue classes exist
- **THEN** default status marks issues_truncated and diagnostics pages preserve all classes without exposing raw private storage

#### Scenario: Diagnostic data changes between pages
- **WHEN** a diagnostic cursor is reused after the underlying grouped result changes
- **THEN** invalid_cursor is returned and pages from different snapshots are never combined silently
