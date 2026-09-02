## ADDED Requirements

### Requirement: Agent interprets factual scope inventory for the Human
The Skill SHALL direct the Agent to read the Tool-provided statistical tree,
expand relevant subtrees when needed, explain observed counts, bytes, kinds,
representative paths, and discovery limits, and label any cache, output, backup,
or legitimacy interpretation as Agent judgment rather than Tool fact.

#### Scenario: Similarity cache contains JPG frames
- **WHEN** the inventory exposes `.similarity_cache` with many JPG descendants
- **THEN** the Agent explains the factual expansion and its interpretation, then helps the Human choose inclusion or exclusion without claiming that the Tool identified a cache

#### Scenario: Hidden directory contains legitimate media
- **WHEN** the inventory exposes a hidden media-bearing directory
- **THEN** the Agent does not treat hiddenness as exclusion authority and asks for Human direction when the intended scope is not already clear

#### Scenario: Ordinary dotfiles dominate node count
- **WHEN** non-media dotfiles are numerous but small
- **THEN** the Agent summarizes them as one factual population and focuses Human attention on choices that can materially change media scope or work

### Requirement: Agent submits only authorized scope choices
The Skill SHALL require the Agent to distinguish its recommendation from Human
or caller authority, submit only the exact accepted default and subtree
exceptions, and report a stale-selection response instead of retrying or
silently broadening the choice.

#### Scenario: Human accepts the Agent proposal
- **WHEN** the Human accepts a proposed default and exception set
- **THEN** the Agent submits that exact selection with the current inventory fingerprint and does not add unreviewed exclusions

#### Scenario: Source changes before execution
- **WHEN** the Tool reports that the accepted inventory is stale
- **THEN** the Agent presents the refreshed factual delta and obtains any newly required direction before resuming

#### Scenario: No Human is available
- **WHEN** an unattended caller has neither a reusable selection nor delegated authority to submit one
- **THEN** the Agent or caller leaves the Run waiting and reports the machine-readable scope requirement instead of treating silence as consent

