> 第6包拟议变更。基线为当前 `docs/spec/contract/plan-work/`；本文件尚未修改现行合约或认证实现。交换形状见本包 `plan-work.tool.json`。

## MODIFIED Requirements

### Requirement: Mutable Working State authority
Tool SHALL own one exact Result binding, open/closed lifecycle, opaque revision, Human preference snapshot, optional working notes, and at most one current organization inside each Work. Organization SHALL be absent, a draft, or a complete candidate; the Tool SHALL NOT maintain independently mutable draft and candidate copies. It SHALL preserve the reserved Plan reference without treating it as published.

#### Scenario: Empty Work is usable
- **WHEN** a Work is created from a trusted plan-ready Result
- **THEN** notes are empty, organization is absent, inspect succeeds, and a current-state view is offered without inventing a directory or Plan scope

#### Scenario: Draft replaces a candidate
- **WHEN** an accepted update supplies a draft as the current organization
- **THEN** the previous candidate and sealable identity are replaced atomically, while the new draft is available for review

### Requirement: Safe request replay
create/update/seal SHALL retain request_id idempotency for the authoritative operation receipt: identical accepted input returns the same business fields and causes no new transition; different input under that ID returns idempotency_conflict. The added view delivery descriptor SHALL be explicitly defined as a fresh observation per invocation and SHALL NOT mutate or replace the original operation receipt. New-interface guarantees SHALL NOT silently reinterpret historical requests from an unsupported interface.

#### Scenario: Lost update reply after another update
- **WHEN** a successful update at revision A is replayed after the Work has reached revision B
- **THEN** the original business receipt still names A, no write occurs, and the view descriptor reports A as superseded with B as its observed current revision

#### Scenario: Delivery recovers between retries
- **WHEN** the operation succeeded but its first view delivery was unavailable and the same request is retried after recovery
- **THEN** business fields remain unchanged while the new view observation can report ready

#### Scenario: Request identity is misused
- **WHEN** an accepted request_id is reused with a different organization or note
- **THEN** the Tool rejects it without saving any supplied field

### Requirement: Atomic candidate replacement
update SHALL require work_ref, current base_revision, request_id, and at least one of organization_content, organization_preferences or working_notes. organization_content SHALL replace candidate_content in the new interface without an alias. Omission preserves; an object replaces the entire organization after validating its declared kind; null clears it. Notes and preferences retain exact omission/replacement/clear semantics. All supplied fields SHALL commit together or not at all. Every new accepted update, including same-value input, SHALL create a new revision; idempotent replay SHALL NOT.

#### Scenario: Save partial organization and a note together
- **WHEN** a valid draft assigns five of eight scoped items and updates working_notes
- **THEN** both are saved under one new revision, the remaining three items stay unassigned, and no sealable identity is issued

#### Scenario: Invalid assignment with a useful note
- **WHEN** a combined update assigns one item twice or references an item outside scope
- **THEN** no organization, note, preference or revision is changed

#### Scenario: Explicit withdrawal
- **WHEN** organization_content is explicitly null
- **THEN** current organization and candidate identity disappear, while notes, preferences and reserved Plan reference remain unless separately changed

#### Scenario: Light save does not invent decisions
- **WHEN** only notes or preferences are saved
- **THEN** the Tool preserves the organization without interpreting the prose, performs no new candidate semantic analysis, and separately reports any derived view reads or delivery limitations

### Requirement: Deterministic candidate validation and identity
Draft validation SHALL require the complete organization field shape, a nonempty Result-local scope, fully resolved references, disjoint assigned outcomes, no assigned members outside scope, safe paths/names and valid decision-note references. Draft validation SHALL permit unassigned scoped members and SHALL NOT invent fallback outcomes. Candidate validation SHALL additionally require full scope coverage and conforming Frozen Plan materialization. Only an explicitly submitted valid candidate SHALL receive candidate_content_identity; full coverage alone SHALL NOT promote a draft. Materialization SHALL omit kind and add the reserved plan_ref and existing contract constant under the unchanged Frozen Plan encoding.

#### Scenario: Full coverage remains a draft
- **WHEN** a draft happens to account for every scoped item
- **THEN** it remains a draft with seal_ready false and no candidate identity

#### Scenario: Candidate has a missing outcome
- **WHEN** an organization declared candidate leaves a scoped item unassigned
- **THEN** the entire update is rejected as organization_invalid

#### Scenario: Empty tree is a complete organization
- **WHEN** every scoped item has an explicit conforming other_outcome and no new directory is required
- **THEN** a candidate can pass complete validation without a populated directory tree

#### Scenario: Source names collide
- **WHEN** assigned filenames collide with one another or a required directory
- **THEN** draft and candidate updates are rejected rather than relying on later Apply to repair the organization

### Requirement: Cursor integrity
inspect SHALL read the current exact revision and support complete or paged organization content. Every cursor SHALL bind Work, revision, selected collection, query shape and continuation position and resist modification. A cursor from another revision SHALL NOT be silently ignored even when organization is absent. The organization kind and any global candidate identity SHALL remain consistent across pages; pagination completion SHALL NOT mean that a draft is a complete candidate.

#### Scenario: Page a partial draft
- **WHEN** a draft has enough saved groups or notes to require multiple pages
- **THEN** pages expose the saved draft under one revision without inventing a candidate identity

#### Scenario: Work changes between pages
- **WHEN** a continuation from revision A is used after a new update
- **THEN** the Tool reports the revision/cursor error and returns no mixed-version page

#### Scenario: Exact references survive restart
- **WHEN** a valid cursor is used after a compatible Host restart and the Work revision is unchanged
- **THEN** continuation remains correct under the existing persisted cursor integrity boundary

### Requirement: Trusted and recoverable sealing
seal SHALL require one complete current candidate, exact request revision and identity, and trusted Human context containing principal_ref, work_ref, reviewed_revision, confirmed_content_identity and confirmed_at. The reviewed Work/revision SHALL equal the requested current Work/revision. No ordinary request, working note, page access or content digest SHALL supply Human authority. Success SHALL preserve the existing atomic publication/recovery behavior, close the exact revision, and return the complete unchanged-format Frozen Plan. Closing SHALL NOT create another organization revision.

#### Scenario: Notes change after acceptance
- **WHEN** the candidate identity is unchanged but an update to working_notes creates a new revision
- **THEN** the old trusted reviewed_revision cannot seal the new revision, including when the Agent has reread that revision

#### Scenario: Same content is restored after withdrawal
- **WHEN** a candidate is withdrawn and later restored with the same identity
- **THEN** its new revision requires new matching Human acceptance

#### Scenario: Only presentation changes
- **WHEN** the reviewer refreshes, pages, or regenerates the same saved version without an update
- **THEN** the Work revision and matching acceptance remain unchanged

#### Scenario: Trusted context names the wrong revision
- **WHEN** the request names the current revision but trusted context names another Work or reviewed revision
- **THEN** seal returns confirmation_binding_mismatch without publication

#### Scenario: Interrupted seal publication
- **WHEN** a reserved seal has produced its verified artifact but not finished the SQLite close transition
- **THEN** the existing matching retry recovers that exact artifact and closes the same revision without another Plan

## ADDED Requirements

### Requirement: Inspect exposes authoritative state independently of rendering
inspect SHALL retain overview, preferences, working_notes, content and validation sections and add view to default selection. Explicit selection SHALL return exactly the requested sections in canonical order. It SHALL return reserved_plan_ref as the Work's preallocated reference: in an open Work it is only reserved, and after seal it matches the published plan_ref. Content SHALL contain the current organization rather than a falsely conforming Frozen Plan draft. Omitting view SHALL permit authoritative state recovery without launching the renderer or view Host. Validation SHALL distinguish normal absent/draft state from save failure and SHALL NOT certify semantic sufficiency or Human acceptance.

#### Scenario: Renderer is broken but notes were saved
- **WHEN** a caller selects overview and working_notes without view
- **THEN** the saved fields and revision remain readable independently of renderer failure

### Requirement: Committed work survives view delivery failure
The Tool SHALL report expected view delivery limitations separately from successful persistence. An unexpected view implementation failure SHALL surface as operation_failed at the outer boundary with the known committed_receipt when available; renderer/test execution SHALL propagate the error and SHALL NOT turn it into a normal missing-image result. No view failure SHALL cause silent rollback, a repeated semantic write or a new confirmation.

#### Scenario: Core save succeeds and the view path is unavailable
- **WHEN** persistence commits but the local display service cannot be reached
- **THEN** the successful operation receipt is preserved and view reports unavailable with a concrete reason

#### Scenario: Unexpected renderer exception after commit
- **WHEN** rendering raises an unexpected implementation exception after successful persistence
- **THEN** the runtime surfaces failure and the actual committed receipt, and a later state-only inspect or matching retry can recover without another write
