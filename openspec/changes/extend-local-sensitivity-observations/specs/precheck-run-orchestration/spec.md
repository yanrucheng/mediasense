> Proposed delta only. Development is not authorized. The [change entry](../../README.md) owns the planning status; docs/spec/contract remains the current public authority. Disabled-model behavior below uses the explicitly recorded planning default D5-disabled.

## MODIFIED Requirements

### Requirement: Execution is configuration- and dependency-driven
The orchestrator SHALL run only capabilities selected by a durable Run configuration and SHALL derive ordering from producer dependencies. It MUST NOT materialize every optional producer merely because one implementation exists. Sensitivity SHALL remain disabled by default and SHALL support an independently selected set of local model profiles. Each selected profile SHALL retain its effective model, input requirements, output declarations, execution settings and resource requirements in the existing Run configuration. Dataset sensitivity configuration SHALL replace the user sensitivity table as a whole.

#### Scenario: Local minimal profile
- **WHEN** embeddings, sensitivity, and external geocoding are disabled
- **THEN** the Run omits them, performs zero network calls, and still completes when its selected evidence is sufficient

#### Scenario: Optional local evidence enabled
- **WHEN** an embedding or sensitivity profile and its local backend are enabled
- **THEN** the producer runs only after its required visual Artifact is available

#### Scenario: Only one sensitivity model is selected
- **WHEN** Freepik is enabled and NudeNet 640 is disabled, or the inverse selection is configured
- **THEN** only the selected model contributes observations to the new Result, while the unselected model has an explicit not_checked explanation and cannot invalidate unrelated valid work

#### Scenario: A disabled model has valid cached output
- **WHEN** a model is disabled for a successor Run even though its prior output remains valid
- **THEN** the new Result excludes that model's cached observations and reports the disabled choice, while prior Results and caches remain intact

#### Scenario: Configuration changes after a Run starts
- **WHEN** the user edits model selection or semantic profile settings before resuming an existing Run
- **THEN** resume uses the original frozen configuration and the changed selection requires a successor Run

## ADDED Requirements

### Requirement: Local adapters share a bounded image and typed observation boundary
A sensitivity adapter SHALL accept identified local prepared images and an explicit effective profile and execution envelope, and SHALL return ordinary typed values or an attributable known failure for every requested input. Its declaration SHALL identify supported inputs, produced attribute kinds, label and score semantics, and local execution requirements without requiring model inference. The stage SHALL own input selection, Work state and Result projection. The adapter MUST NOT read stage-private storage, upload inputs, automatically download assets, or choose Plan policy.

#### Scenario: Another classifier uses different labels
- **WHEN** a supported adapter declares a different categorical taxonomy and conforms to the classification-distribution value semantics
- **THEN** the same producer and reader accept its defined labels without a brand-specific orchestration or consumer branch

#### Scenario: Batch output cannot be matched to inputs
- **WHEN** an adapter returns a duplicate input key, missing row or unassignable extra row
- **THEN** the boundary rejects the invalid output before attribution or successful publication and surfaces the execution defect

### Requirement: Each local model has honest resource and backend execution
Each model SHALL use its own declared device, precision and batch settings under the existing resource admission mechanism. Model residency and per-batch work SHALL have an accounted resource lifetime. The runtime SHALL distinguish enforced limits, estimates and measured use, verify the actual backend, and report unknown measurements as unknown. It MUST NOT understate a demand by clamping it to capacity, fabricate per-image timing from batch averages, or silently change device, model or locality.

#### Scenario: Selected Freepik and NudeNet recipes execute together
- **WHEN** both selected profiles require fresh work
- **THEN** Freepik uses MPS FP32 with batch 4 and actual tail batches, NudeNet 640 uses CPU FP32 with batch 1, and embedding's batch setting does not control either model

#### Scenario: A library ignores a requested provider
- **WHEN** the underlying library uses a backend different from the selected profile
- **THEN** execution is rejected or corrected within that exact profile before claiming success, and provenance reports the backend actually used

#### Scenario: A model remains loaded between batches
- **WHEN** its batch reservation ends but model memory remains resident
- **THEN** the existing admission/accounting scope continues to own the resident demand instead of treating that memory as free

### Requirement: Sensitivity reuse follows semantic dependencies
Work reuse SHALL bind the actual input identity, model and processor content, effective preprocessing, postprocessing, output semantics and result-affecting implementation/runtime settings. A change to one model SHALL NOT invalidate unrelated model or preparation work. Pure scheduling changes SHALL NOT invalidate results when they do not affect semantics or validity. Valid completed output SHALL be reusable without loading its producing model, with retained provenance and an explicit reuse outcome.

#### Scenario: Only Freepik's semantic recipe changes
- **WHEN** source input, prepared Evidence, NudeNet and embedding dependencies are unchanged
- **THEN** only affected Freepik work is recomputed and unrelated valid work is reused

#### Scenario: The model is absent but an exact valid result is cached
- **WHEN** all selected work for that model can be proven reusable from committed output
- **THEN** the Run reuses it without model loading and reports reuse rather than new inference

#### Scenario: Native NMS settings change
- **WHEN** only post-NMS instances were retained and the requested NMS differs
- **THEN** the runtime requires new work for that model rather than claiming suppressed candidates can be recovered from old boxes

### Requirement: Required model work distinguishes prerequisites from failures
When selected fresh work cannot execute because its pinned local assets or backend are unavailable, the Run SHALL preserve completed work, expose the known prerequisite and recovery condition, and withhold successful Result publication. Known localized failures SHALL remain attributable to their actual input and SHALL preserve unrelated successful work. Unexpected exceptions and protocol or invariant violations SHALL surface as execution or Host failures and MUST NOT be reclassified as normal waits, disabled capabilities, empty detections or corrupt source media without evidence.

#### Scenario: Selected model needs fresh inference but weights are missing
- **WHEN** no valid cached output can satisfy that requested work
- **THEN** the Run reports the existing backend-unavailable blocking condition and the exact prerequisite without automatic download, silent skip or remote fallback

#### Scenario: One image fails while another succeeds
- **WHEN** the adapter has a known per-input failure with reliable input correspondence
- **THEN** that observation records failed with provenance and basis, while successful siblings remain committed and can be delivered under the existing qualified-result rules

#### Scenario: An implementation invariant is violated
- **WHEN** orchestration or result assembly raises an unexpected implementation error
- **THEN** the failure is exposed immediately with bounded diagnostics and is not converted to paused or blocked
