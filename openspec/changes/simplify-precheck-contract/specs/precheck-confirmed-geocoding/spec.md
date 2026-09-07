## MODIFIED Requirements

### Requirement: PreCheck remains local-first with one bounded external exception
PreCheck SHALL perform zero external effects until matching trusted authority exists. It SHALL use media-aware conservative geographic acquisition units and the shared mediasense.geo.query boundary for selected coordinate-only work. It SHALL NOT transmit source media, renditions, embeddings, paths, filenames, prompts or general metadata. Missing location SHALL NOT itself prevent planning.

#### Scenario: Default run
- **WHEN** geographic acquisition is disabled by the selected local policy
- **THEN** no Provider requests occur and truthful not_checked observations do not alone block Plan

#### Scenario: Authorized frozen batch
- **WHEN** a media-aware compressed query set receives matching trusted authority
- **THEN** the shared Geo Tool executes only within its declared request and retry ceilings

#### Scenario: Disallowed payload
- **WHEN** acquisition would transmit unauthorized data classes
- **THEN** it is rejected before transmission

### Requirement: Query scope is frozen after compression
PreCheck SHALL use local companion, bundle, time, coordinate and trajectory evidence to derive conservative acquisition units, then apply exact-coordinate deduplication as final request defense. It SHALL freeze the effective query set and profile before confirmation, and project outcomes to every covered Source Item without promoting bundle membership to location truth.

#### Scenario: Duplicate representative coordinates
- **WHEN** multiple acquisition units have the same effective coordinate
- **THEN** one authorized logical query may cover them while every Source Item retains a qualified projected outcome

#### Scenario: Changed frozen set
- **WHEN** coordinate membership, bounds or effective retry/profile semantics change
- **THEN** earlier authority cannot authorize changed effects

### Requirement: Confirmation is an automatic Run checkpoint
Before admitting external requests PreCheck SHALL enter its confirmation pause, expose the full exact disclosure and use trusted Host elicitation. Proceed SHALL bind the full disclosure and request identity, decline SHALL terminate without publication, and dismissal SHALL leave the Run paused. There SHALL be no skip_optional_work bypass under this contract.

#### Scenario: Confirmation required
- **WHEN** authorized geographic work is pending
- **THEN** no new request occurs before the exact Provider, coordinate, ceiling, cost-unknown and retention disclosure is accepted

#### Scenario: Skip or cancel
- **WHEN** the Human declines or caller cancels
- **THEN** no new Provider request is admitted and no fictitious Provider refusal or successful Result is produced

#### Scenario: Disclosure exceeds a response page
- **WHEN** the frozen coordinates require several read pages
- **THEN** all pages bind one content identity and no partial or per-page consent substitutes for complete Human confirmation

### Requirement: Effects and candidate semantics remain observable
The Result SHALL preserve per-Source-Item address_candidate and nearby_place_candidates Observations, original sources and limits, and an auditable execution boundary. available SHALL have a usable value; non-available statuses SHALL have no value. no_result SHALL map to missing, terminal known failure to failed with basis, and partial useful results SHALL remain independently available. Ordinary missing locations SHALL NOT invalidate publication or Plan readiness.

#### Scenario: Provider fallback
- **WHEN** one logical query makes multiple Provider requests
- **THEN** audit distinguishes actual attempts, historical reused requests and current effects without exposing those as Plan-required fields

#### Scenario: Provider returns no result or failure
- **WHEN** both components yield no_result or end in known failure
- **THEN** normalized non-available observations seal successfully, remain distinguishable, and do not alone block Plan

#### Scenario: Only one component succeeds
- **WHEN** address succeeds while nearby places fail
- **THEN** address value survives, nearby_places is failed without value, and its limitation is visible

### Requirement: Reuse includes routing semantics but excludes credentials
Geo reuse SHALL depend on coordinate and effective operation/profile/bounds, not previous unrelated batch position. New and retained results SHALL pass the same pure normalization boundary; unsupported legacy component facts SHALL remain not_checked rather than invented no_result. Credentials SHALL NOT enter identity or evidence. Reuse SHALL NOT confer new external authority.

#### Scenario: Reused prefix
- **WHEN** previously committed equivalent observations can satisfy current acquisition
- **THEN** they are reused with original provenance, zero new requests and complete per-source projection

#### Scenario: Different sequence context
- **WHEN** another coordinate is inserted or reordered without changing this coordinate's effective semantics
- **THEN** valid reuse and normalized meaning remain stable

#### Scenario: Legacy aggregate missing
- **WHEN** an old aggregate record cannot prove both components were executed
- **THEN** unknown components are explicitly not_checked with historical_geo_unrecorded and no network request or fabricated candidate is generated
