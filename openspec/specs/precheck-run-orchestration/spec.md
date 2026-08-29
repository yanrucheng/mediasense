# precheck-run-orchestration Specification

## Purpose
TBD - created by archiving change complete-precheck-run-orchestration. Update Purpose after archive.
## Requirements
### Requirement: A configured Run drives the complete PreCheck chain
The `mediasense.precheck.run` implementation SHALL durably prepare and
immediately return a source-bound configured Run. An internal host worker SHALL
then coordinate discovery/accounting, required Work, Artifact production,
Evidence assembly, validation, and automatic immutable Result publication
without requiring the caller to invoke individual producers or seal manually.

#### Scenario: Small mixed Dataset
- **WHEN** a configured Run starts for supported image, video, and auxiliary inputs
- **THEN** `start` immediately returns its `run_ref`, the host worker executes the required local producer graph, and a later status returns one verified `published_result`

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
The orchestrator SHALL stop admitting new work when the Run is paused or
cancelled. A localized media/producer failure SHALL remain attached to that item
and SHALL NOT discard successful siblings. An unrecoverable orchestration or
seal-integrity failure SHALL produce an honest blocked or failed Run state.

#### Scenario: One corrupt image
- **WHEN** one image cannot be decoded and another succeeds
- **THEN** the successful item remains usable and the failed item has an explicit exception route in the Result

#### Scenario: Pause and resume
- **WHEN** an external caller pauses a running worker and later resumes the Run
- **THEN** both controls return independently of the worker, no new work starts while paused, and a rescheduled worker continues from durable state

#### Scenario: Cancel
- **WHEN** cancellation is accepted
- **THEN** no new work or Result is published for that Run

### Requirement: Completion is gated by closure and immutable publication
The orchestrator SHALL publish only after accounting, navigation, Work/Artifact,
source-verification, and Result integrity gates pass. Publication SHALL recover
idempotently across crashes before or after Result registration.

#### Scenario: Seal succeeds
- **WHEN** every selected gate succeeds
- **THEN** Run status becomes `completed` and references the exact readable immutable Result

#### Scenario: Seal crash window
- **WHEN** execution stops after Result bytes are published or registered but before Run completion
- **THEN** retry adopts or reuses the one matching Result and never reports partial success

### Requirement: Repeated compression creates independent Results
Distinct declared compression targets SHALL produce independent immutable
Results while reusing semantically valid lower-level Work and Artifact bytes.

#### Scenario: 500 to 3 to 200
- **WHEN** three Runs process the same unchanged 500-item Dataset with targets 500, 3, and 200
- **THEN** their entry counts match those targets, Result references are distinct, and low-level Work and Artifact production is not repeated

