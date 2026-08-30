## ADDED Requirements

### Requirement: Preview exposes material Plan-owned Geo evidence without acquiring it
The preview SHALL show any Plan-owned Geo observation that materially supports a
candidate name or grouping together with its candidate status, provenance,
qualifications, and distinction from Agent judgment and Human confirmation. Preview
rendering SHALL NOT invoke the Geo Tool or any provider.

#### Scenario: Candidate uses Plan-owned place evidence
- **WHEN** a candidate name or grouping is supported by an accepted Plan Geo observation
- **THEN** the preview makes the observation basis and its qualifications reviewable under the exact revision

#### Scenario: Preview is regenerated
- **WHEN** a preview containing Plan-owned Geo evidence is regenerated from the same exact Working State revision
- **THEN** it uses the stored observation, performs zero provider requests, and preserves the same logical evidence presentation
