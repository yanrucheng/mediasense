## ADDED Requirements

### Requirement: Preview is bound to exact candidate content
The preview capability SHALL render one exact Plan Working State revision and candidate content identity. A preview SHALL identify the bound Work, revision, and identity so it cannot be mistaken for another candidate.

#### Scenario: Render a current candidate
- **WHEN** preview is requested for an exact available revision
- **THEN** the rendered result identifies that revision and its candidate content identity

#### Scenario: Candidate changes after rendering
- **WHEN** an update creates a new revision after a preview was rendered
- **THEN** the old preview remains attributable to the old revision and cannot authorize sealing the new revision

### Requirement: Preview exposes the complete review structure
The preview SHALL expose the proposed final directory hierarchy, the number of expanded media members in every directory, one or two available representative visual items per directory, and every explicit `other_outcome` relevant to scope closure.

#### Scenario: Review a populated directory
- **WHEN** a logical directory contains viewable represented media
- **THEN** the preview shows its exact member count and deterministic representative samples without changing membership

#### Scenario: Representative evidence is unavailable
- **WHEN** a directory has no accessible qualifying rendition
- **THEN** the preview reports the unavailable sample honestly and does not substitute an untraceable image or hide the directory

### Requirement: Preview supports bounded drill-down
The preview capability SHALL let a reviewer expand a logical directory and inspect its members in bounded pages without requiring the entire Dataset to be embedded in one document.

#### Scenario: Expand a large directory
- **WHEN** a reviewer requests details for a directory whose members exceed one page
- **THEN** the preview returns a stable page bound to the same revision and provides a continuation path until the directory is complete

### Requirement: Preview is deterministic and non-authoritative
The same exact candidate, PreCheck Result, and rendering profile SHALL produce the same logical preview content and ordering. Preview files and views SHALL be regenerable derived artifacts and SHALL NOT replace Working State, PreCheck Evidence, or the Frozen Plan.

#### Scenario: Regenerate a preview
- **WHEN** the same exact inputs are rendered again after a prior preview is discarded
- **THEN** the logical tree, counts, sample selection, outcomes, and ordering are equivalent

### Requirement: Preview performs no semantic or external side effects
The renderer SHALL derive its output from existing Plan and PreCheck authorities. It SHALL NOT alter candidate organization, select new semantic groups, mutate source media, call reverse-geocoding services, upload media, or make billable model requests.

#### Scenario: Render under zero-egress conditions
- **WHEN** a preview is generated from locally available evidence
- **THEN** it completes without network dependencies and reports unavailable local evidence explicitly

### Requirement: Preview presentation is validated by a Human reference review
Before the preview presentation contract is finalized, the implementation SHALL produce one representative preview from the existing Mock and pause for Human review of comprehensibility, navigation, evidence visibility, and revision identity.

#### Scenario: First reference preview is ready
- **WHEN** the first representative preview meets automated structural checks
- **THEN** implementation pauses for Human review before treating its presentation shape as accepted

