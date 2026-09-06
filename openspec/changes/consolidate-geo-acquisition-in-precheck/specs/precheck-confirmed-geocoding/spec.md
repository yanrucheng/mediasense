## MODIFIED Requirements

### Requirement: PreCheck remains local-first with one bounded external exception
PreCheck SHALL perform zero external calls by default. After local compression
has frozen a non-empty Geo acquisition set, the Run MAY call the stage-neutral
`mediasense.geo.query` Tool under trusted Human authority bound to that exact
request and its hard effect envelope. It MUST NOT transmit source media,
renditions, embeddings, paths, filenames, prompts, or general metadata.

#### Scenario: No coordinates apply
- **WHEN** no Source Item has an available final coordinate
- **THEN** PreCheck records Geo as `not_applicable`, makes zero Geo Tool or Provider calls, and may publish

#### Scenario: Provider exists but authority does not
- **WHEN** a non-empty compressed query set has a compatible Provider and no matching trusted authority
- **THEN** PreCheck pauses with `confirmation_required` after a zero-effect Geo Tool preflight

#### Scenario: Disallowed payload
- **WHEN** a caller attempts to include media, paths, filenames, prompts, or unrelated metadata in the Geo request
- **THEN** the Geo Tool rejects it before any Provider effect

## ADDED Requirements

### Requirement: Coverage and acquisition cardinality remain separate
Every Source Item with an available final coordinate SHALL receive its own
place outcome containing separate address and nearby-place component outcomes
before a Result is Plan-ready. PreCheck SHALL NOT infer that each covered Source
Item requires a distinct logical query.

#### Scenario: One observation covers a stationary burst
- **WHEN** bundle, temporal, and coordinate evidence supports one stationary acquisition unit containing multiple located Source Items
- **THEN** PreCheck issues one logical query and projects its outcome to every member

#### Scenario: Visual compression selects fewer representatives
- **WHEN** adaptive visual compression selects fewer representative media than the located Source Item population
- **THEN** Geo coverage still includes every located Source Item and does not use the visual target count as its query contract

#### Scenario: A located Source Item has no outcome
- **WHEN** Result assembly finds any Source Item with a final coordinate but no address-and-nearby-place outcome
- **THEN** the Result is blocked from Plan-ready handoff

### Requirement: PreCheck obtains complete bounded place evidence
PreCheck SHALL submit a bounded `resolve_place` request whose exact identity and
authorization envelope cover both address and nearby-place acquisition. Each
component SHALL preserve its own `success`, `no_result`, `failed`,
`indeterminate`, or `not_requested` status.

#### Scenario: AMap returns address and POI together
- **WHEN** AMap satisfies a bounded place resolution from one `extensions=all` response
- **THEN** the Tool emits address and nearby-place components and counts one Provider request

#### Scenario: Google returns address and POI separately
- **WHEN** Google satisfies a bounded place resolution through reverse-geocode and nearby-place endpoints
- **THEN** the Tool emits both components and counts the two Provider requests separately

#### Scenario: Nearby lookup has no candidate
- **WHEN** address acquisition succeeds and the executed nearby-place request returns no candidate
- **THEN** the Source Item retains the address and an explicit nearby-place `no_result`, not `not_requested`

#### Scenario: Nearby lookup fails after address succeeds
- **WHEN** bounded fallback cannot complete nearby-place acquisition after address success
- **THEN** the outcome is partial, preserves the address, and carries the nearby failure qualification

#### Scenario: A Provider effect is indeterminate
- **WHEN** an admitted address or nearby-place effect has no known terminal result
- **THEN** the journal preserves `indeterminate` and replay does not issue that effect again

### Requirement: Bundle evidence is candidate scope rather than inherited truth
PreCheck SHALL use existing asset association, bundle membership, capture time,
coordinate, and GPX evidence to form Geo acquisition units. It SHALL split a
candidate when local evidence indicates movement, incompatible datums, coordinate
conflict, or insufficient temporal support. No bundle representative is an
unconditional location surrogate.

#### Scenario: Same asset variants agree
- **WHEN** RAW/JPG/sidecar variants in one deterministic asset association have locally consistent coordinates
- **THEN** they MAY share one Geo observation

#### Scenario: A temporal chain moves
- **WHEN** successive items belong to one bundle but their trajectory coordinates exceed the active stationary-consistency method
- **THEN** PreCheck splits the chain into multiple acquisition units before Geo invocation

#### Scenario: Time or coordinate evidence conflicts
- **WHEN** a bundle's local evidence cannot support one stationary unit
- **THEN** PreCheck preserves smaller units or independent queries rather than assigning the representative's place to all members

#### Scenario: Adaptive visual groups exist
- **WHEN** adaptive compression groups media for bounded visual review
- **THEN** those groups do not by themselves establish Geo equivalence

## MODIFIED Requirements

### Requirement: Query scope is frozen after compression
After acquisition-unit formation, PreCheck SHALL choose a deterministic actual
member coordinate for each unit, deduplicate exact equal Provider inputs, exclude
already reusable complete address-and-nearby observations, and freeze the
remaining bounded Geo Tool request before requesting authorization. Nearby radius
and result count SHALL be part of the frozen identity. Approximate spatial matching
SHALL remain an internal, versioned PreCheck method and SHALL NOT become a
cross-stage invariant.

#### Scenario: Duplicate coordinates remain after unit formation
- **WHEN** multiple acquisition units select the same normalized coordinate
- **THEN** the frozen Tool request contains one logical query while all Source Item outcome mappings remain intact

#### Scenario: Frozen pending set changes
- **WHEN** the effective pending coordinate set, operation, locale, retention, or Provider envelope changes
- **THEN** the prior authorization does not authorize the changed request

### Requirement: Confirmation is an automatic Run checkpoint
The PreCheck Run SHALL expose one exact confirmation for the pending shared-Tool
request. The disclosure SHALL distinguish covered Source Item outcomes, total
logical observations, compatible cache reuse, pending logical queries, Providers,
data classes, maximum Provider requests, billable-unit knowledge, and retention.

#### Scenario: Human proceeds
- **WHEN** trusted confirmation names the exact Geo request fingerprint
- **THEN** PreCheck invokes that request only within the Tool-enforced envelope

#### Scenario: Human declines
- **WHEN** the Human declines the required Geo effect
- **THEN** the Run becomes cancelled and sends no Provider request

#### Scenario: Provider is unavailable
- **WHEN** the Geo Tool preflight reports no compatible configured Provider
- **THEN** the Run fails with `provider_unavailable` before asking for authorization

### Requirement: Effects and candidate semantics remain observable
Each completed Geo Tool component SHALL remain a candidate observation with its
status, Provider, input and Provider coordinates, actual Provider-request count,
qualification, and observed time. A no-result or localized failure is an explicit
outcome rather than an omitted Source Item.

#### Scenario: Provider fallback
- **WHEN** one logical query attempts more than one authorized Provider
- **THEN** the Result distinguishes the logical query from every observed Provider request

#### Scenario: Provider returns no result or failure
- **WHEN** the Provider returns no candidate or a localized failure
- **THEN** the mapped Source Items retain an explicit missing or failed outcome

### Requirement: Reuse includes routing semantics but excludes credentials
Place-observation identity SHALL depend on normalized coordinate, address and
nearby-place operation scope, nearby bounds, locale, effective Provider/routing
semantics, and refresh policy. It SHALL NOT depend on previous Work, query
position, bundle identity, or Source Item membership.

#### Scenario: A coordinate is inserted before cached coordinates
- **WHEN** a successor Run adds or reorders coordinates while the effective observation semantics remain unchanged
- **THEN** compatible successful observations retain their reusable identities

#### Scenario: Compatible 0.7.1 observation exists
- **WHEN** an old successful observation demonstrably contains the characterized address-and-POI semantics and matches coordinate, profile, refresh policy, and language
- **THEN** PreCheck migrates it locally into the stable identity without a Provider request

## ADDED Requirements

### Requirement: Per-item place evidence excludes acquisition mechanics
The immutable Result SHALL expose one qualified place outcome, including address
and nearby-place component outcomes, on every located Source Item. It SHALL NOT
require Plan to know bundle formation, unit membership, cache hits, routing state,
request identity, or retry mechanics.

#### Scenario: Provider returns no result or failure
- **WHEN** the authorized Tool completes a coordinate with no candidate or a localized failure
- **THEN** every mapped Source Item receives an explicit missing or failed outcome with qualifications

#### Scenario: One observation is shared
- **WHEN** one Tool component serves multiple Source Items
- **THEN** Result projection gives each Source Item its own outcome and keeps acquisition internals out of the Plan contract

## ADDED Requirements

### Requirement: PreCheck exposes distinct Geo accounting dimensions
PreCheck SHALL keep Source Item outcomes, logical queries, compatible cache hits,
Provider requests, and authorized request ceilings distinct in Run disclosure and
Result effect evidence.

#### Scenario: Compressed batch contains cached observations
- **WHEN** some acquisition units reuse compatible Work and others require Provider access
- **THEN** the disclosure reports total outcomes, total logical queries, cache reuse, pending logical queries, and the pending Provider-request ceiling separately
