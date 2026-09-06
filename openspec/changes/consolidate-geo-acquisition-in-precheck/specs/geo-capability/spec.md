## MODIFIED Requirements

### Requirement: Bounded resolve may acquire address and nearby-place evidence
An unbounded `resolve_place` request SHALL retain the least-expansive
address-first behavior and MAY return a separately authorized continuation. A
`resolve_place` request carrying both `radius_meters` and `max_places` SHALL bind
and execute both `reverse_geocode` and `nearby_places` components under one exact
request identity and effect envelope. Supplying only one bound SHALL be invalid.

#### Scenario: AMap coalesces compatible components
- **WHEN** AMap can return address and nearby places from one bounded regeo request
- **THEN** both component outcomes are returned while one Provider request is counted

#### Scenario: Google requires separate endpoints
- **WHEN** Google resolves the same bounded request through reverse and nearby endpoints
- **THEN** both Provider requests count against the request-wide hard ceiling

#### Scenario: Default Plan lookup remains progressive
- **WHEN** a caller submits `resolve_place` without nearby bounds
- **THEN** the Tool preserves the address-first result and separately authorized nearby continuation

### Requirement: Every external effect is bound to exact authority
Every Geo Provider effect SHALL require trusted authority for the exact canonical
request fingerprint and a machine-enforced envelope covering Provider identities,
data classes, logical queries, Provider requests, billable-unit policy, and
retention. The Provider-request ceiling SHALL apply to the whole invocation,
including retries and fallback, and SHALL be checked before each request.

#### Scenario: First live lookup requires authorization
- **WHEN** any caller submits a valid Geo request without trusted authority
- **THEN** the Tool returns `authorization_required`, the exact request fingerprint, and the proposed hard envelope while sending zero Provider requests

#### Scenario: Provider fallback reaches the ceiling
- **WHEN** another Provider attempt would exceed the authorized batch ceiling
- **THEN** the Tool does not start that attempt and returns an explicit failed or not-requested component

#### Scenario: A frozen request changes
- **WHEN** operation, coordinate subjects, locale, options, or retention changes
- **THEN** prior authority does not authorize the changed request

### Requirement: Routing and caller state remain isolated
Provider routing SHALL be scoped to one Tool invocation and SHALL NOT leak mutable
state across callers. Every coordinate in a batch SHALL begin from the request's
declared route context so insertion or reordering of another coordinate does not
silently change its Provider/language semantics. Any returned route context is an
explicit hint for a future caller request, not hidden shared state.

#### Scenario: PreCheck and Plan calls overlap
- **WHEN** PreCheck and Plan invoke Geo concurrently or sequentially
- **THEN** neither call changes the other's route selection, authorization, retention, or result identity

#### Scenario: Batch subjects are reordered
- **WHEN** the same subjects and semantics are supplied in another order
- **THEN** the canonical request fingerprint is unchanged and each coordinate begins from the same route seed

### Requirement: Effectful request replay is safe
The Geo Tool SHALL durably admit an authorized request before its first Provider
effect. Reuse of the same request ID and canonical request SHALL replay the
retained terminal or indeterminate result without another authorization prompt or
Provider effect. If authority is supplied on replay, it SHALL match the original
binding.

#### Scenario: Successful response was lost
- **WHEN** the same authorized request is retried after its terminal response was not received
- **THEN** the Tool returns the journaled result and makes no additional Provider request

#### Scenario: Request ID is reused with changed authority
- **WHEN** a request ID names different canonical input or authority
- **THEN** the Tool returns `idempotency_conflict` before a Provider effect

#### Scenario: Prior Provider effect is indeterminate
- **WHEN** the process cannot prove whether an admitted Provider effect completed
- **THEN** replay returns `indeterminate` and does not automatically repeat the request
