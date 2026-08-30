## ADDED Requirements

### Requirement: Plan-owned Geo observations remain epistemically and operationally separate
Plan Working State SHALL retain any accepted Geo observation with its exact
PreCheck Result and subject binding, authorization evidence, normalized candidate
content, provenance, qualifications, observed effects, and request outcome. It
SHALL keep that observation distinguishable from immutable PreCheck facts, Agent
judgment, organization decisions, and Human confirmation, and SHALL NOT copy or
mutate the PreCheck Result.

#### Scenario: Authorized observation is stored
- **WHEN** a Plan-owned Geo request returns candidate evidence
- **THEN** Plan can inspect the observation and its provenance under the exact bound Result without promoting it to confirmed place truth

#### Scenario: Identical request is replayed
- **WHEN** an identical Plan Geo request is retried after its response was lost
- **THEN** Plan returns or recovers the original recorded outcome without creating an indistinguishable second observation or silently repeating provider effects

#### Scenario: Authorization is stale
- **WHEN** a request changes its coordinate, operation, provider constraints, request ceiling, cost ceiling, or retention from the authorized request
- **THEN** Plan records no new provider observation and the Geo boundary requires new authority

### Requirement: Geo enrichment does not weaken the Plan stage boundary
Plan Geo integration SHALL remain read-only with respect to source media and SHALL
invoke the Geo capability only with values obtained through the exact PreCheck Read
contract or already stored Plan-owned Geo observations. It SHALL NOT read PreCheck
SQLite, Work, caches, provider credentials, or internal runtime records.

#### Scenario: Plan selects a coordinate for enrichment
- **WHEN** the Agent requests Geo evidence for a Source Item in the bound Result
- **THEN** the adapter resolves the coordinate through contracted Result content and performs no private PreCheck read

### Requirement: Geo observation storage is revision-bound and idempotent
The existing `mediasense.plan.work` Tool SHALL provide `enrich_geo` as the
Plan-owned coordination action. Authorization preflight or refusal SHALL preserve
the current revision. Persisting a terminal Geo outcome SHALL atomically append its
observation and authorization evidence, advance the Working State revision, and
apply Plan request-id replay semantics.

#### Scenario: Geo authorization is required
- **WHEN** `enrich_geo` reaches the Geo boundary without matching authority
- **THEN** it returns the proposed Geo authorization requirement and leaves Plan Working State unchanged

#### Scenario: Geo observation is persisted
- **WHEN** an authorized Geo request returns a terminal observation outcome
- **THEN** Plan stores it under a new revision while preserving the existing candidate and immutable Result binding

#### Scenario: Plan enrichment response is lost
- **WHEN** an identical `enrich_geo` request is replayed after its Plan state transition completed
- **THEN** the Tool returns the recorded response without another revision or provider request
