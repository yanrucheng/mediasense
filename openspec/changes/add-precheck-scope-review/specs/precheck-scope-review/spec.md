## ADDED Requirements

### Requirement: PreCheck exposes a factual bounded source inventory
Before expensive work is admitted, `mediasense.precheck.run` SHALL expose a
deterministic statistical tree derived from the complete current discovery.
The inventory SHALL report file and byte totals, deterministic file-kind and
size distributions, representative source-relative paths, discovery limits,
and bounded tree structure without assigning semantic cache, output, backup,
legitimacy, confidence, or recommendation labels.

#### Scenario: Media-bearing dot directory is discovered
- **WHEN** the source contains `.similarity_cache` with JPG files
- **THEN** the inventory reports that path, its JPG count, bytes, distributions, and bounded descendants without declaring that it is a cache or excluding it

#### Scenario: Legal hidden media remains factual
- **WHEN** a hidden directory contains supported media and no selection has excluded it
- **THEN** the inventory reports the hidden relative path and media facts without treating hiddenness as a scope decision

#### Scenario: Large tree is bounded
- **WHEN** the source tree exceeds one response's node or depth budget
- **THEN** the Tool returns aggregate facts, omitted-child counts, and a continuation when needed and permits the caller to request a bounded subtree or later sibling page through `status`

#### Scenario: Discovery is incomplete
- **WHEN** a directory cannot be read or a size cannot be observed
- **THEN** the inventory reports the issue or unknown value and does not present its totals as complete

### Requirement: Expensive work requires an exact scope selection
The Run SHALL NOT admit metadata extraction, full-content verification,
decoding, rendition, video probing or frame extraction, embedding, sensitivity,
compression, reverse geocoding, or other expensive producer Work until an exact
scope selection is accepted for the current inventory.

#### Scenario: First Run reaches scope review
- **WHEN** initial discovery and accounting complete without a reusable selection
- **THEN** the Run pauses with `scope_confirmation_required` and no expensive producer Work has been admitted

#### Scenario: Unattended caller supplies no selection
- **WHEN** no caller responds to the scope-review pause
- **THEN** the durable Run remains waiting with machine-readable inventory facts and admits no expensive Work

### Requirement: Scope selection is simple and complete
A scope selection SHALL identify the exact inventory fingerprint, one default
disposition of `include` or `exclude`, and zero or more pairwise non-overlapping
source-relative subtree exceptions that take the opposite disposition. The Tool
SHALL reject paths outside the inventory, traversal paths, conflicting
exceptions, and decisions for another inventory.

#### Scenario: Default include excludes a cache-shaped subtree
- **WHEN** the caller submits default `include` with `.similarity_cache` as an `exclude` exception for the current inventory
- **THEN** all other discoveries retain normal classification and every discovery in that subtree receives excluded scope

#### Scenario: Default exclude includes one hidden media subtree
- **WHEN** the caller submits default `exclude` with a hidden media directory as an `include` exception
- **THEN** discoveries in that subtree retain their normal media or auxiliary classification and all other discoveries receive excluded scope

#### Scenario: Selection paths overlap
- **WHEN** one exception is an ancestor of another exception
- **THEN** the Tool rejects the ambiguous selection without changing Run scope or admitting expensive Work

### Requirement: Scope decisions remain accounted and auditable
The Working Run SHALL durably retain the inventory identity and accepted
selection. The immutable Result SHALL account for every discovered item and
SHALL retain scope-selection provenance for each item whose scope was changed to
excluded. Exclusion SHALL NOT delete, move, rename, or otherwise modify source
content.

#### Scenario: Excluded JPG cache frames reach the Result
- **WHEN** a confirmed selection excludes a subtree containing JPG files and the Run publishes a Result
- **THEN** those files remain reachable through `accounts_for` with excluded scope and selection basis but have no expensive media Work

#### Scenario: Many ordinary dotfiles are reviewed
- **WHEN** a source contains many non-media dotfiles
- **THEN** their counts and bytes remain visible without requiring one response node per file and their final dispositions remain accounted

### Requirement: Changed source scope invalidates stale selection
Before admitting expensive Work following a scope decision, PreCheck SHALL
reconcile the discovery boundary again. A materially different factual
inventory SHALL prevent application of the old selection, preserve the attempted
decision for audit, and expose a new inventory requiring a new selection.

#### Scenario: JPG appears after confirmation
- **WHEN** a JPG is added beneath a selected or excluded subtree after the inventory was presented
- **THEN** the old selection does not authorize the changed inventory and the new JPG enters a refreshed scope review before expensive processing

#### Scenario: Unchanged inventory reuses a prior selection
- **WHEN** a later Run over the same Dataset produces the exact compatible inventory fingerprint
- **THEN** it may reuse the prior selection while recording its provenance and without editing the prior Run or Result

### Requirement: Tool facts and semantic judgment remain separate
The Tool SHALL report filesystem and accounting observations and SHALL enforce
the caller's exact selection. It MUST NOT infer that a discovered path is a
cache, historical output, backup, or unwanted media from its name or hidden
status.

#### Scenario: Cache-like name contains original media
- **WHEN** a directory has a cache-like or hidden name but contains media the Human intends to organize
- **THEN** the Tool leaves that intent unresolved until the Agent or caller supplies an include/exclude selection
