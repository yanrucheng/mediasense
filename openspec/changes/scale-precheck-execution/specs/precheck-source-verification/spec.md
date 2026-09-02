## MODIFIED Requirements

### Requirement: Verification is a replaceable Source Item observation
PreCheck SHALL allow an eligible Source Item to carry a
`source_content_verification` observation. An available observation SHALL contain
a named verification profile, verification value, byte length, observation time,
producer identity, limitations where applicable, and basis linking it to that
Source Item. The profile SHALL state whether it detects ordinary revision/stat/
fingerprint change or proves exact bytes. The profile and value MUST NOT become
Source Item identity, and absence of a PreCheck exact-byte observation MUST NOT
alone make an otherwise eligible Source Item unselectable by Plan.

#### Scenario: Exact profile is deliberately produced
- **WHEN** PreCheck reads all bytes of an eligible regular source file with stable pre/post file observations
- **THEN** it may publish profile `sha256-full-v1`, a `sha256:` value, exact byte length, observation time, and producer provenance

#### Scenario: Ordinary-change profile is sufficient
- **WHEN** PreCheck binds Work to the accounted Source revision and bounded fingerprint and stable pre/post file observations show no ordinary change
- **THEN** it may reuse or publish the limited observation without re-reading every source byte and records that limitation explicitly

#### Scenario: Source Item has no exact PreCheck proof
- **WHEN** a Source Item is accounted and otherwise eligible but PreCheck did not select it for exact proof
- **THEN** the Result does not fabricate exact verification, Plan may still reference the Source Item, and Apply remains responsible for establishing exact selected-effect proof

### Requirement: Seal revalidates projected source verification
Before publishing a Result, PreCheck SHALL revalidate every available source
verification observation included in that Result according to its declared
profile against the same bound Working Run. For an ordinary-change profile,
matching Source revision, bounded fingerprint, and current file identity SHALL
be sufficient; Seal MUST NOT upgrade a limited observation into an exact-byte
claim. A changed, missing, or mismatched source MUST prevent publication of a
Result that presents the observation as current.

#### Scenario: Ordinary source identity remains stable
- **WHEN** the accounted revision, bounded fingerprint, and current file identity still match a limited observation at the seal gate
- **THEN** Seal accepts that observation without a full-byte reread and preserves its stated limitations

#### Scenario: Source changes after observation
- **WHEN** revision, fingerprint, size, modification time, inode-visible identity, or availability no longer matches at the seal gate
- **THEN** no Result presenting that observation as current is published

### Requirement: Plan preserves references and Apply verifies selected effects
Plan SHALL freeze the exact `result_ref` and selected `source_item_ref` values
without copying verification values into Frozen Plan. During preparation, Apply
SHALL resolve those references through `mediasense.precheck.read`, safely bind
each selected locator's declared `source_root_ref`, read the selected source
bytes with an exact supported profile, and retain the exact result in the
existing prepared operation state. Immediately before each authorized file
operation, Apply SHALL recheck the selected source against that prepared exact
result.

#### Scenario: Selected source had no exact PreCheck observation
- **WHEN** Apply safely binds an eligible selected Source Item whose Result carries only limited or no source verification
- **THEN** Apply establishes the exact supported proof during preparation and may proceed only after all other safety gates succeed

#### Scenario: Selected source matches at the effect boundary
- **WHEN** the current byte length and exact verification value match the prepared selected-source proof
- **THEN** source verification permits the already-authorized operation to proceed to its remaining deterministic gates

#### Scenario: Verification cannot be established
- **WHEN** the source root cannot be safely bound, the exact profile is unavailable, preparation cannot read the selected bytes, or current bytes differ from the prepared proof
- **THEN** Apply blocks that operation without inventing a replacement source or changing plan semantics
