> 本轮用户已明确授权并接受本包信息/失败边界；对应语义已采用到 `docs/spec/contract/`。此处保留 change delta，当前合约仍是唯一交换值权威。

## ADDED Requirements

### Requirement: Sensitivity observations retain typed model-specific information
The existing content_sensitivity Observation SHALL retain model/profile identity and typed named values with their label system, score semantics, basis and qualifications. The initial supported values SHALL be classification distributions, cumulative event probabilities and region instances. A profile SHALL declare which values it provides and requires. A consumer MUST NOT infer an absent value kind is a negative result, require every model to emit all kinds, or treat an unknown extension as a completed check.

#### Scenario: Freepik returns four mutually exclusive classes
- **WHEN** the selected Freepik profile succeeds
- **THEN** the Observation contains all neutral, low, medium and high probabilities and the three cumulative events, with explicit class/event meanings and checked sum relationships

#### Scenario: A classifier provides no location information
- **WHEN** its profile declares classification attributes only
- **THEN** its Observation has no fabricated empty region-detection value

#### Scenario: A future output has a different mathematical meaning
- **WHEN** a model produces independent multi-label scores or logits instead of a categorical probability distribution
- **THEN** it requires a defined value semantic through the existing extension process and cannot pass as a normalized exclusive distribution

### Requirement: Region instances remain complete and tied to the actual input
Each region instance SHALL retain its label, model score and position, including multiple instances of the same label and native labels that do not imply sensitivity. Coordinates SHALL identify the actual prepared input's oriented pixel space and dimensions. Available and failed sensitivity observations SHALL reference their real input Evidence in the bound Result. Read and display consumers MUST NOT promote an input observation to unexamined video frames or represented members.

#### Scenario: Two regions have the same body label
- **WHEN** NudeNet returns two separate native boxes with the same label
- **THEN** both boxes and both scores survive production, sealing and Read without label-max aggregation

#### Scenario: Native xywh is projected to xyxy
- **WHEN** the native result supplies an integer x, y, width and height
- **THEN** projection preserves x, y, x+width and y+height against the input Evidence dimensions without another clipping, rounding or NMS pass

#### Scenario: A sampled frame represents a video
- **WHEN** sensitivity was evaluated on one prepared video-frame Evidence
- **THEN** Read attributes the observation to that exact frame input and retains the source/derivation limits without a whole-video conclusion

### Requirement: Sensitivity absence and completion remain distinguishable
Observation status/value rules SHALL remain available, missing, failed, not_checked and not_applicable with the existing meanings. Successful region detection with no retained instances SHALL use available with an empty instance list and its effective profile. Disabled, unprepared, unsupported and failed outcomes SHALL carry specific basis and known identity without invented execution facts. The same subject's observations SHALL be unambiguous by detector/profile binding and actual input, including non-executed declarations.

#### Scenario: NudeNet executes and returns no boxes
- **WHEN** its requested input was processed successfully under the declared native thresholds
- **THEN** instances is empty within an available value and the observation does not claim the subject has no relevant real-world content

#### Scenario: A disabled model is not installed
- **WHEN** the frozen configuration disables that declared model
- **THEN** the result records not_checked and the configured model/profile without loading it, inventing an observed execution time, or returning a negative score

#### Scenario: No prepared input exists
- **WHEN** a Source Item was not selected for expensive visual preparation
- **THEN** the result reports evidence_not_prepared without creating a false input Evidence reference

### Requirement: Sensitivity reading is independent of inference installation
Sealed sensitivity results SHALL retain the values and public definitions, provenance, input binding and material limits necessary to read them without the producing model, inference library, mutable configuration or private cache. The existing Read interface SHALL preserve historical V1 label/score/threshold/mild_threshold/sensitive/mild_sensitive meanings and sealed bytes. Missing historical information SHALL remain explicitly unknown rather than reconstructed as current successful output.

#### Scenario: The model and optional inference packages are removed
- **WHEN** a valid retained Result is read through the installed Host
- **THEN** its saved observations remain readable without importing or loading those model backends

#### Scenario: A historical V1 result has no boxes
- **WHEN** the old record retained only label maxima and thresholds, including 99 and 33
- **THEN** Read preserves those values and identifies unrecorded locations/instances instead of inventing empty boxes or a full instance list

#### Scenario: An observation or page grows beyond its existing bound
- **WHEN** complete region instances make a response exceed the current size limit
- **THEN** Read preserves the existing whole-item pagination and explicit too-large behavior without truncating detections or rewriting the Result

### Requirement: Conflicting sensitivity outputs remain attributed evidence
Read SHALL preserve each model's actual result, input, profile and score meaning independently. Neither production nor reading SHALL merge models by equal label text, compare unlike scores as a common probability, fabricate a fused sensitivity truth, or infer permission for remote processing. Plan SHALL retain ownership of interpretation and user policy.

#### Scenario: A classifier is neutral while a detector finds a body region
- **WHEN** both model operations succeeded
- **THEN** both available observations remain visible and their different semantics can be inspected without selecting a winning model in the result layer
