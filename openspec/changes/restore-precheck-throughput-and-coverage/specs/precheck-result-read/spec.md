> 本次实施需求已在用户委托判断/开发的授权下收敛，交换值已定义在当前 Read schema。
> `sample_time_seconds` 保留请求位置含义，`decoded_time_seconds` 是可选的实际 PTS；历史 Result 不改写。

## ADDED Requirements

### Requirement: Video evidence distinguishes sampling intent from observed position
Prepared video Evidence SHALL expose its actual source binding and the frame position/precision that the producer can prove. A requested seek position MUST NOT be presented as an exact observed frame timestamp merely because it was passed to a decoder. Material selection offsets or unavailable precision SHALL remain explicit through the existing Observation, basis, provenance and qualification structure. A change to the meaning of a named public field SHALL require an explicitly reviewed contract change.

#### Scenario: A requested location resolves to an earlier available frame
- **WHEN** a temporal request near the end resolves to a frame whose proven PTS is 8.2082 seconds
- **THEN** the Evidence does not assert that it is a frame at the container endpoint or original requested time, and material selection limitations are available to its reader

#### Scenario: Exact decoded position cannot be proven
- **WHEN** an adapter can prove the sampled image but cannot prove its exact timestamp
- **THEN** the result preserves the supported position description and uncertainty rather than fabricating exact precision

#### Scenario: Historical evidence lacks actual-position proof
- **WHEN** an immutable historical Result records a sampling value without proof of actual decoded position
- **THEN** its bytes and original meaning remain intact, the limitation is retained where it can be established from the Result, and Read does not silently repair it from mutable Work or newly read source bytes

### Requirement: Evidence preparation coverage remains separate from source accounting
Read SHALL preserve the distinction between complete source accounting, representation relationships, actually acquired visual material and finite-sampling limitations. Material unfulfilled preparation and successful evidence SHALL remain inspectable using existing Source Items, Evidence, relations and attributes. Neither a valid represents relationship nor plan_ready SHALL be promoted into a claim that all represented content was visually inspected or that all downstream semantic questions are resolved.

#### Scenario: A video is represented by one usable frame
- **WHEN** a video has a valid route to one prepared Evidence item and additional selected sampling attempts failed
- **THEN** its actual material and failures remain visible, and structural readability does not assert full temporal coverage or successful key-frame ranking

#### Scenario: One Evidence represents many Source Items
- **WHEN** an Evidence item is derived from one source and represents additional members
- **THEN** sampling and image attributes remain attached to the actual derivation, while represents retains the distinct member scope and limitations

### Requirement: Better preparation produces successor evidence without rewriting prior results
Changes to sampling or other semantic preparation dependencies SHALL produce or reuse Work according to their real dependency differences and SHALL publish changed authoritative evidence only in a successor Result. Unaffected valid outputs SHALL remain reusable. Read SHALL remain read-only over its exact Result and MUST NOT create new frames or a new authoritative quality state during a query.

#### Scenario: Corrected sampling reuses unrelated metadata
- **WHEN** a new preparation method corrects video sampling while source bytes and metadata semantics remain unchanged
- **THEN** the new Run can reuse valid metadata and unaffected materials, publish its changed frame evidence in a successor Result and leave prior Result bytes unchanged

#### Scenario: A reader requests unprepared temporal detail
- **WHEN** a consumer requests evidence beyond the Result's retained preparation
- **THEN** Read preserves its existing read boundary and explains the available material or limitation without silently launching decoding or altering the Result
