## MODIFIED Requirements

### Requirement: PreCheck remains local-first with one bounded external exception
PreCheck SHALL perform zero external calls by default. After compression has
selected and frozen its representative-coordinate batch, a Run with a non-empty
batch SHALL acquire coordinate-level reverse-geocode evidence before Result
publication and SHALL require trusted Human authority bound to that exact batch
and provider-policy disclosure. It MUST NOT transmit source media, renditions,
embeddings, paths, filenames, prompts, or general metadata.

#### Scenario: No coordinates apply
- **WHEN** the frozen representative batch contains no available GPS or GPX coordinate
- **THEN** Geo acquisition is `not_applicable`, zero provider requests occur, and PreCheck may continue to Result publication

#### Scenario: Provider exists but authority does not
- **WHEN** a non-empty frozen batch has a compatible configured provider but no matching trusted Human authority
- **THEN** the Run pauses with `authorization_required`, reports the exact disclosure, performs zero provider and network requests, and publishes no Result

#### Scenario: Disallowed payload
- **WHEN** an acquisition path would transmit anything beyond normalized coordinates, datum, and required lookup locale
- **THEN** PreCheck refuses the external work before transmission

### Requirement: Query scope is frozen after compression
The runtime SHALL derive reverse-geocode inputs only from the completed
compression frontier, apply GPX-over-embedded-GPS precedence per Source Item,
normalize coordinates, deduplicate exact `(latitude, longitude, datum)` triples,
and freeze the ordered logical-query set before requesting authorization. The Run
SHALL retain a full-batch identity for reuse and routing semantics and derive a
separate external-effect identity from only the queries that remain uncomputed,
their exact disclosure, and the parent full-batch identity. Selection,
authorization binding, Work reuse, and Result projection SHALL remain owned by
that PreCheck Run and SHALL NOT be inherited from Plan state.

#### Scenario: Duplicate representative coordinates
- **WHEN** multiple selected representatives have the same exact normalized coordinate triple
- **THEN** the frozen set contains one logical query and retains a Result-bound Source Set containing every member Source Item

#### Scenario: Conflicting GPS and GPX coordinates
- **WHEN** one Source Item has differing available GPS and GPX observations
- **THEN** the frozen batch uses the declared GPX precedence while the Result and Geo summary preserve the conflict count and both source observations

#### Scenario: Changed frozen set or disclosure
- **WHEN** coordinates, provider set, provider policy, request ceiling, cost knowledge, or operation changes after an earlier confirmation
- **THEN** the earlier confirmation does not authorize the changed work and no provider request occurs

#### Scenario: Frozen batch mixes reused and pending coordinates
- **WHEN** a frozen batch contains reusable completed queries and uncomputed queries
- **THEN** the full-batch identity retains both classes while the external-effect disclosure, logical-query count, exact coordinates, request ceiling, and confirmation identity contain only the uncomputed queries

### Requirement: Confirmation is an automatic Run checkpoint
PreCheck SHALL enter `paused` before the first provider request for a non-empty
pending effect set with available providers and expose one content-addressed
disclosure containing only its exact coordinates, operation, transmitted data
classes, provider identities, maximum provider requests, known cost ceiling or
`unknown`, provider data-handling policy or `unknown`, fixed immutable-Result
retention, and parent frozen-batch identity. `proceed` SHALL require
transport-only trusted Human confirmation bound to that exact effect identity.

#### Scenario: Confirmation required
- **WHEN** uncomputed logical queries have a compatible configured provider
- **THEN** status reports the exact disclosure and no provider or network request occurs before matching trusted confirmation

#### Scenario: Human declines
- **WHEN** the Human submits `decline` for the pending disclosure
- **THEN** the Run terminates as non-success with `authorization_declined`, performs zero new provider requests, and publishes no Result

#### Scenario: Proceed lacks trusted authority
- **WHEN** a caller submits `proceed` without trusted confirmation bound to the disclosure identity
- **THEN** the Tool returns `authorization_required`, leaves the Run paused, performs zero provider requests, and publishes no Result

#### Scenario: Unknown provider policy is accepted explicitly
- **WHEN** provider data handling is `unknown` and the Human confirms the exact disclosure identity containing that value
- **THEN** the Run may proceed within the disclosed envelope without representing the policy as `none`

### Requirement: Effects and candidate semantics remain observable
The Result SHALL identify each reverse-geocode output as provider-derived
candidate Evidence and retain exact Source Set membership, provider, language,
input and provider datum, observation time, route attempts, fallback or partial
failure, logical-query count, actual provider-request count, and an explicit
billable-cost value or `unknown`. Accepted observations SHALL have immutable
Result retention and no caller-selectable retention mode.

#### Scenario: Provider fallback
- **WHEN** one logical query uses more than one provider request
- **THEN** the Result distinguishes the one logical query from every observed provider request and its outcome

#### Scenario: Provider returns no result
- **WHEN** an authorized lookup completes with no candidate
- **THEN** the Result records `no_result` as an executed candidate observation and does not infer that the real-world place does not exist

#### Scenario: One coordinate fails
- **WHEN** one authorized coordinate fails while other frozen coordinates complete
- **THEN** the Result preserves the failed component and qualification separately from successful or no-result components

#### Scenario: Provider is globally unavailable
- **WHEN** a non-empty frozen batch has no compatible configured provider
- **THEN** the Run terminates with `provider_unavailable` before authorization is requested and publishes no Result

### Requirement: Reuse includes routing semantics but excludes credentials
Reusable geocode Work SHALL depend on the normalized coordinate, effective
provider/routing profile, preceding route observation when continuity affects the
next lookup, and applicable provider-policy disclosure. Credentials MUST NOT enter
Work identity, persisted output, Result content, or logs.

#### Scenario: Reused prefix
- **WHEN** a prior query is reused in an otherwise equivalent ordered batch
- **THEN** its recorded next provider/language state drives the following query without repeating the reused provider call

#### Scenario: Different sequence or policy context
- **WHEN** the same coordinate follows a different route observation or provider-policy disclosure
- **THEN** it does not silently reuse a result whose effective acquisition semantics differ

## ADDED Requirements

### Requirement: PreCheck Read exposes a deterministic Geo summary
`mediasense.precheck.read` SHALL expose a paged `geo_summary` operation derived
only from one verified immutable Result. It SHALL report GPS/GPX observation-state
counts, combined available/missing/failed/conflicting counts, the exact
deduplication rule, unique-coordinate count, and for each coordinate its member
count, compact Result-bound Source Set resolvable through the existing paged
`resolve` operation, acquisition outcome, candidate Evidence refs, provenance,
and qualifications. It SHALL NOT embed an unbounded member list or create event
semantics, place truth, recommended grouping, or directory names.

#### Scenario: Summary matches exhaustive traversal
- **WHEN** a caller exhausts every page of `geo_summary` and independently traverses every Source Item and Geo candidate Evidence in the same Result
- **THEN** coordinate keys, membership, outcome counts, provenance, and qualifications are identical

#### Scenario: One coordinate represents many Source Items
- **WHEN** one coordinate group contains more member refs than fit in a Tool response
- **THEN** `geo_summary` returns a bounded Result-local relationship Source Set whose exact members can be exhausted through `resolve` without `response_item_too_large`

#### Scenario: Old Result omitted required acquisition
- **WHEN** a Result contains an available coordinate but no completed candidate Evidence for that coordinate
- **THEN** `geo_summary` reports overall acquisition `incomplete` even if the historical Result readiness field says `plan_ready`
