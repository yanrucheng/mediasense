## ADDED Requirements

### Requirement: Ordinary Runs accept complete preparation requirements
The Run Tool SHALL accept optional explicit source_set and complete Processing Profile values on ordinary start. A source_set SHALL bind one trusted prior Result's complete accounted input snapshot. Omitted settings SHALL resolve current Dataset defaults and SHALL NOT inherit from prior_result_ref. Changed requirements SHALL create a new ordinary Run, while resume SHALL retain the original frozen requirements.

#### Scenario: Caller requests a local refinement
- **WHEN** the caller supplies the full input snapshot S and a Profile with override T
- **THEN** the Tool creates an ordinary Run whose output still accounts for S and whose selected T uses the complete override settings

#### Scenario: Prior association is not inheritance
- **WHEN** start supplies prior_result_ref without explicit preparation values
- **THEN** current defaults and ordinary discovery apply, and the Tool does not merge old configuration or source selection

#### Scenario: Invalid scope is refused
- **WHEN** overrides overlap, select an empty/non-processable set, or the outer snapshot is incomplete
- **THEN** the Tool refuses invalid_source_set before producer effects

#### Scenario: A selected reference is outside its Result
- **WHEN** a source selector contains an unknown or out-of-Result reference
- **THEN** the Tool preserves reference_not_in_result rather than guessing a source or scanning another Dataset

### Requirement: Other preparation settings are explicitly guarded
A supplied Profile SHALL bind the content identity of effective non-editable preparation semantics. The Tool SHALL compare the current projection before accepting a new request, SHALL refuse configuration_changed on mismatch, and SHALL NOT interpret the identity as permission, a cache key or an old-Profile lookup operation.

#### Scenario: Dataset model defaults changed
- **WHEN** a caller submits a copied Profile whose configuration identity no longer matches current preparation settings
- **THEN** no new Run is created and configuration_changed explains the mismatch

#### Scenario: Existing idempotent request is replayed
- **WHEN** the same accepted canonical request_id and request content are replayed after defaults change
- **THEN** the existing Run is returned without re-resolving the new defaults or starting another worker

### Requirement: Local settings have honest dependency effects
The Tool SHALL apply complete compression values to disjoint declared partitions. Other parameters SHALL remain as declared, while derived groups MAY change through actual dependencies. It SHALL expand cross-boundary representative membership before selected-source preparation and SHALL preserve the distinction between source observations and representative coverage.

#### Scenario: A representative spans the selection boundary
- **WHEN** T includes only some members represented by existing Evidence
- **THEN** selected and remaining source membership is resolved explicitly and the old representative's own observations are not copied to unobserved members

#### Scenario: Count fallback changes remaining groups
- **WHEN** the configured fallback depends on the remaining participating inputs
- **THEN** new remaining groups may differ, and Read exposes their actual members and basis without claiming unchanged parameters imply unchanged grouping

### Requirement: Reuse follows capability dependencies
The Run SHALL compose independent capability demands and SHALL reuse outputs whose actual inputs, semantic producer settings and validity remain unchanged. A Run ID or unrelated Profile change SHALL NOT by itself invalidate all work. Missing local inputs SHALL be prepared only within declared source, resource and effect boundaries.

#### Scenario: Only a content threshold changes
- **WHEN** all input evidence and enabled encoder settings remain valid
- **THEN** no metadata extraction, decoding or embedding inference is repeated solely because a new Run or threshold exists

#### Scenario: A disabled comparison cannot implement a threshold change
- **WHEN** an override changes content_distance_scale while content comparison is disabled
- **THEN** configuration_invalid is returned rather than silently enabling a model or pretending the change took effect

### Requirement: Results retain preparation and input binding evidence
A completed new Result SHALL seal its effective Profile, exact override memberships and qualified direct input bindings as Result-owned data. These SHALL remain available independently of mutable Run/Work records and evictable producer caches. Source revision mismatch SHALL NOT be silently accepted as the requested prior input.

#### Scenario: Publication is retried
- **WHEN** a Run resumes after an interrupted publication
- **THEN** it publishes at most its one immutable Result and retains valid sibling work

#### Scenario: Producer cache is evicted
- **WHEN** replaceable cached producer output is removed after publication
- **THEN** retained Result-owned material and preparation evidence remain readable under the existing retention contract
