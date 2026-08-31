## MODIFIED Requirements

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
