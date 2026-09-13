## ADDED Requirements

### Requirement: Preparation can be read as a reusable value
The existing review operation SHALL support an optional preparation view containing the current Result's explicit accounted Source Set and complete reusable Profile. It SHALL derive the view from sealed Result data, SHALL NOT start preparation, and SHALL NOT reconstruct history from mutable Run state.

#### Scenario: Caller prepares the next request
- **WHEN** review includes preparation for a Result produced under this contract
- **THEN** the returned value can be copied into a new ordinary start with this Result as the source-reference context, without private storage access

#### Scenario: Historical preparation was not recorded
- **WHEN** a trusted historical Result lacks sealed preparation data
- **THEN** preparation is null with processing_profile_unrecorded, while its other supported reads remain available

### Requirement: Saved profile scopes are bounded Source Set expressions
Source Set SHALL support profile_scope with a nonnegative index into the bound Result's frozen override membership. This SHALL be a value-position selector with no independent lifecycle. Resolve SHALL read its exact saved members with existing pagination and digest semantics rather than rerun compression or recursively interpret a self-reference.

#### Scenario: Large saved selection is copied
- **WHEN** a saved override covers 100000 sources
- **THEN** preparation readback uses one profile_scope selector and resolve can separately page its complete exact membership

#### Scenario: Scope position does not exist
- **WHEN** the requested position is outside the frozen Profile or the Result lacks preparation data
- **THEN** resolve returns invalid_source_set without substituting all sources or current defaults

### Requirement: Correspondence is supported by sealed direct input bindings
Resolve MAY take target_result_ref and SHALL then return one qualified correspondence outcome per original member and echo the target Result in resolution. Matched SHALL require a unique sealed direct input binding and matching observed revision under its stated verification profile. Independent path or content similarity SHALL NOT establish correspondence. Missing proof SHALL return unproven without a target reference.

#### Scenario: Direct successor retains an input occurrence
- **WHEN** the target was explicitly prepared from the source Result and preserves the observed input binding
- **THEN** resolve returns its target Result-local Source Item reference with the actual verification basis and limitations

#### Scenario: Two files share bytes
- **WHEN** two original source occurrences have equal content digests
- **THEN** they remain separately mapped by recorded input occurrence, and no content-based deduplication collapses their identities

#### Scenario: Target has no recorded input relationship
- **WHEN** the target is an independently prepared or historical Result without the required lineage
- **THEN** correspondence is unproven even if paths and digests resemble the original inputs

### Requirement: Cross-Result pagination preserves both bindings
A correspondence cursor SHALL bind both immutable Result digests and the original selector, limit, order and position. Original source_set_identity and membership_identity SHALL retain their existing definitions. Result integrity failures SHALL remain call-level errors rather than convenient unproven rows.

#### Scenario: Target changes between pages
- **WHEN** a cursor is reused with another target_result_ref
- **THEN** the Tool returns invalid_cursor

#### Scenario: Recorded binding is contradictory
- **WHEN** a supposedly matched sealed binding refers outside the declared input or collapses distinct occurrences
- **THEN** Result validation rejects the inconsistency rather than returning an arbitrary target
