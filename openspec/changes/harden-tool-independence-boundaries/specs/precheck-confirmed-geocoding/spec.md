## MODIFIED Requirements

### Requirement: PreCheck remains local-first with one bounded external exception
PreCheck SHALL perform zero external calls by default. After compression has
selected and frozen its representative-coordinate batch, an enabled Run MAY
perform coordinate-level reverse geocoding under authority bound to that exact
Run batch. It MUST NOT transmit source media, renditions, embeddings, paths,
filenames, prompts, or general metadata. PreCheck MAY use its own batch engine and
fixed Run profile; it is not required to expose Plan's per-request interaction or
to invoke `mediasense.geo.query`.

#### Scenario: Default run
- **WHEN** a Run does not explicitly enable reverse geocoding
- **THEN** it performs zero provider requests and can complete through the local path

#### Scenario: Authorized frozen batch
- **WHEN** a Run freezes a deduplicated coordinate batch and obtains matching Run-scoped authority
- **THEN** PreCheck may execute the batch under its selected fixed provider/routing profile and records its exact effects

#### Scenario: Disallowed payload
- **WHEN** an enabled producer would transmit anything beyond normalized coordinates and required lookup parameters
- **THEN** PreCheck refuses that external work before transmission

### Requirement: Query scope is frozen after compression
The runtime SHALL derive reverse-geocode inputs only from the completed
compression frontier, normalize and deduplicate identical coordinates, and
freeze the ordered logical-query set before requesting Run-scoped authorization.
Selection, authorization binding, Work reuse, and Result projection SHALL remain
owned by that PreCheck Run and SHALL NOT be inherited from Plan state.

#### Scenario: Duplicate representative coordinates
- **WHEN** multiple selected representatives have the same normalized coordinate
- **THEN** the frozen set contains one logical query and retains all represented Source Item links

#### Scenario: Changed frozen set
- **WHEN** the query set or effective provider profile changes after an earlier decision
- **THEN** the earlier decision does not authorize the changed work and the Run pauses again

### Requirement: Confirmation is an automatic Run checkpoint
Before the first provider request, the Run SHALL enter `paused` and report the
exact number of pending logical queries. One matching `proceed` decision SHALL
authorize the complete fingerprinted frozen batch; PreCheck SHALL NOT require
per-coordinate confirmation. `skip_optional_work` SHALL continue without calls.

#### Scenario: Confirmation required
- **WHEN** enabled reverse geocoding has uncomputed logical queries
- **THEN** status reports their exact count and no provider request occurs before a matching `proceed`

#### Scenario: Skip or cancel
- **WHEN** the user skips the optional work or cancels the Run
- **THEN** no new provider request is admitted and PreCheck records no fictitious Geo Tool refusal
