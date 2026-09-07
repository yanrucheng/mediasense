## MODIFIED Requirements

### Requirement: Apply owns trustworthy Source Set expansion
Production Apply SHALL expand explicit, accounts_for, represents, union and difference Source Sets through the repository-owned deterministic resolver bound to the Frozen Plan's exact result_ref and Dataset, using the public PreCheck Read action=resolve contract. It SHALL preserve selection and membership digest checks, actual array counting, stable order, duplicate rejection, cursor binding/progress, final total membership and source verification requirements. It SHALL NOT read private PreCheck SQLite or accept caller completeness as proof. Removing redundant response fields SHALL NOT remove these checks.

#### Scenario: Traversal silently omits a member
- **WHEN** an adapter returns inconsistent totals, repeats a cursor, duplicates a member, crosses the bound Result or ends before all members are present
- **THEN** Apply rejects preparation rather than producing a smaller operation set

#### Scenario: Test supplies a fake resolver
- **WHEN** an internal test injects a resolver into the lower-level Apply store
- **THEN** that seam is not exposed as public authority or used to bypass production validation

#### Scenario: Compact final page
- **WHEN** resolve returns no returned/complete fields but has a null next_cursor
- **THEN** Apply counts the actual members and recomputes membership identity before accepting completeness
