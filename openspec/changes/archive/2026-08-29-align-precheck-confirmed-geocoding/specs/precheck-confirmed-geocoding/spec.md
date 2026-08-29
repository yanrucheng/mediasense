## ADDED Requirements

### Requirement: PreCheck remains local-first with one bounded external exception
PreCheck SHALL disable external calls by default. The only currently permitted
PreCheck network capability SHALL be coordinate-only reverse geocoding after
compression; it MUST NOT transmit source media, renditions, embeddings, prompts,
or general metadata.

#### Scenario: Default run
- **WHEN** a Run does not explicitly enable reverse geocoding
- **THEN** it performs zero provider requests and can complete through the local path

#### Scenario: Disallowed payload
- **WHEN** an enabled producer would transmit anything beyond the normalized coordinate and required lookup parameters
- **THEN** PreCheck refuses that external work

### Requirement: Query scope is frozen after compression
The runtime SHALL derive reverse-geocode inputs only from the completed
compression frontier, normalize and deduplicate identical coordinates, and
freeze the ordered logical-query set before requesting authorization.

#### Scenario: Duplicate representative coordinates
- **WHEN** multiple selected representatives have the same normalized coordinate
- **THEN** the frozen set contains one logical query and retains all represented Source Item links

#### Scenario: Changed frozen set
- **WHEN** the query set or effective provider profile changes after an earlier decision
- **THEN** the earlier decision does not authorize the changed work and the Run pauses again

### Requirement: Confirmation is an automatic Run checkpoint
Before the first provider request, the Run SHALL enter `paused` and report the
exact number of pending logical queries. `proceed` SHALL authorize only the
fingerprinted frozen set, and `skip_optional_work` SHALL continue without calls.

#### Scenario: Confirmation required
- **WHEN** enabled reverse geocoding has uncomputed logical queries
- **THEN** status reports their exact count and no provider request occurs before a matching `proceed`

#### Scenario: Skip or cancel
- **WHEN** the user skips the optional work or cancels the Run
- **THEN** no new provider request is admitted

### Requirement: Effects and candidate semantics remain observable
The Result SHALL identify reverse-geocode output as provider-derived candidate
Evidence and retain provider, language, input and provider datum, observation
time, route attempts, fallback or partial failure, logical-query count, actual
provider-request count, and an explicit billable-cost value or `unknown`.

#### Scenario: Provider fallback
- **WHEN** one logical query uses more than one provider request
- **THEN** the Result distinguishes the one logical query from every observed provider request and its outcome

#### Scenario: Provider returns no result or failure
- **WHEN** an authorized lookup returns no candidate, partial data, or failure
- **THEN** the corresponding observation state is distinguishable and is not promoted to confirmed place truth

### Requirement: Reuse includes routing semantics but excludes credentials
Reusable geocode Work SHALL depend on the normalized coordinate, effective
provider/routing profile, and preceding route-observation Work when continuity
affects the next lookup. Credentials MUST NOT enter Work identity, persisted
output, Result content, or logs.

#### Scenario: Reused prefix
- **WHEN** a prior query is reused in an otherwise equivalent ordered batch
- **THEN** its recorded next provider/language state drives the following query without repeating the reused provider call

#### Scenario: Different sequence context
- **WHEN** the same coordinate follows a different route-observation Work
- **THEN** it does not silently reuse a result whose provider/language context differs
