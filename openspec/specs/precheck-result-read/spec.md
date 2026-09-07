## Requirements

### Requirement: Read binds an exact trusted immutable Result
The existing mediasense.precheck.read Tool SHALL expose review, expand, resolve and geo_summary via flat action and dataset_ref inputs. It SHALL validate integrity before returning data, reject wrong Dataset references, perform no acquisition or writes, and use the packet contracts as the unique public shape. Query failure SHALL be error; successfully read failed observations SHALL remain data.

#### Scenario: Corrupt sealed Result
- **WHEN** its digest, reference integrity or Observation contract is invalid
- **THEN** Read returns result_untrusted or result_inconsistent and never a fabricated integrity:valid

#### Scenario: Expected missing observation
- **WHEN** an existing Source Item records missing capture time
- **THEN** expand successfully returns missing without a value


### Requirement: Review separates global accounting from review cards
Review SHALL return result, complete global accounting, a page of cards and page continuation. It SHALL preserve scope/condition distinctions, exception paths, overlap, role evidence, field-state counts, material qualifiers and estimated expansion sizes. Execution costs SHALL remain available through explicit execution_boundary include. Derivable counts and success constants SHALL NOT be repeated.

#### Scenario: Five accounted objects include only three media
- **WHEN** the Result contains two usable photos, an invalid video, a GPX input and an excluded file
- **THEN** accounting reports each scope/condition independently and never calls all five photos

#### Scenario: Represented membership overlaps
- **WHEN** one Source Item appears under multiple entry Evidence
- **THEN** global memberships and unique represented counts retain that difference, and cards are not summed as a media total

#### Scenario: Missing or unreported facts
- **WHEN** a member has no capture_time Observation at all
- **THEN** the summary uses unreported rather than falsely claiming missing


### Requirement: Expand preserves exact selected evidence detail
Expand SHALL accept exactly one selector type with at most sixteen refs, explicit includes and atomic validation. It SHALL preserve all selected observations, member-specific coverage basis, provenance, prepared targets of either source_item or evidence kind, available roles and qualifications. member_observations SHALL page one selected Evidence at a time.

#### Scenario: Batch contains one foreign reference
- **WHEN** any selected reference lies outside the bound Result
- **THEN** the whole request fails without partial-success data or foreign-reference disclosure

#### Scenario: Prepared target has no role
- **WHEN** an already prepared Evidence is unclassified by role
- **THEN** it remains reachable rather than disappearing from expansion

#### Scenario: Source Item has no visual Evidence
- **WHEN** a corrupt video has an explicit exception route
- **THEN** its exact source identity, failure basis and empty covering_evidence remain readable


### Requirement: Resolve proves complete membership without private storage
Resolve SHALL support the existing explicit, Result accounts_for, Evidence represents, union, difference and exact geo_coordinate selectors. It SHALL return members in source-ref order with locator, scope, condition and source content verification. Every page SHALL bind source_set_identity and membership_identity; final assembled membership SHALL be rechecked against total and identities by consumers. A resolved set SHALL NOT imply semantic grouping or content verification.

#### Scenario: Lost page or repeated member
- **WHEN** pages omit, reorder or duplicate a Source Item
- **THEN** Plan/Apply Source Set consumption rejects the set rather than accepting caller completeness

#### Scenario: Weak source verification
- **WHEN** a member has only not_checked or weak verification
- **THEN** resolve preserves that fact and Apply retains its independent stronger validation requirement


### Requirement: Paging removes redundancy without losing boundary checks
Paged responses SHALL contain exact total and mandatory next_cursor, with null only for a complete terminal page. Array length SHALL replace returned; next_cursor SHALL replace complete. Byte-limit stops SHALL remain explicit. Cursors SHALL bind Result digest, action, selector, includes, order and limit, remain usable after restart, and reject changed binding. Responses SHALL respect 524288 UTF-8 bytes and complete-item boundaries.

#### Scenario: First page is incomplete
- **WHEN** limit or byte bound ends a page before all members
- **THEN** a nonempty continuation is returned and the caller must not claim complete resolution

#### Scenario: Cursor is applied to another selector
- **WHEN** any bound field differs
- **THEN** Read returns invalid_cursor with no silent restart or mixed membership

#### Scenario: One item exceeds the response bound
- **WHEN** a complete indivisible item cannot fit
- **THEN** response_item_too_large is returned rather than truncating it


### Requirement: Geo diagnostics preserve components without governing Plan entry
Geo summary SHALL count GPS, GPX and final coordinate observations independently and expose coordinate groups with exact source_set selectors. Each group SHALL report per-Source-Item outcome counts for address and nearby_places, not equate candidate availability with both operations succeeding. acquisition_status SHALL describe recorded acquisition closure and SHALL NOT replace readiness. Full attempt/cost audit SHALL remain available separately.

#### Scenario: Same coordinate has mixed historical outcomes
- **WHEN** two Source Items have different qualified component outcomes at one final coordinate
- **THEN** component counts preserve both rather than choosing one aggregate success

#### Scenario: Both components fail with known effects
- **WHEN** acquisition terminated and neither component produced a candidate
- **THEN** geo summary records failure counts while a valid plan_ready Result remains possible


### Requirement: Old evidence is normalized without rewriting history
Read and Geo reuse SHALL share a pure normalization path for retained evidence. Valid sealed Result bytes SHALL remain immutable. Only provable component facts SHALL be projected; unavailable historical proof SHALL become explicit not_checked with basis, and malformed sealed content SHALL be rejected. Normalization SHALL NOT perform Provider requests or inherit historical consent as new authority.

#### Scenario: Valid old result lacks separate component records
- **WHEN** retained data cannot prove that nearby lookup ran
- **THEN** the new projection reports historical_geo_unrecorded rather than inventing no_result

#### Scenario: Legacy Work carries illegal missing value
- **WHEN** a mutable old Work has sufficient separate outcome evidence for conversion
- **THEN** a new normalized v4 Work uses legal observations without modifying old output or relaxing Result validation
