> 本次实施需求已在用户委托判断/开发的授权下收敛，并落入当前 Run/Read 合约。
> 公开权威仍为 `docs/spec/contract/`；数值验收与适用范围见本 change 的 acceptance.md。

## ADDED Requirements

### Requirement: Preparation fulfillment is distinct from terminal work accounting
PreCheck SHALL retain the confirmed source scope, effective preparation obligations and semantic profile through existing Run and Work mechanisms. It SHALL distinguish actual available evidence, legitimate missing information, unrequested work and failed acquisition. Terminal progress and complete source accounting MUST NOT alone be used to claim that the selected preparation obligations or release-quality gates were satisfied. This requirement SHALL NOT silently redefine existing Result readiness or turn every legitimate local gap into a Run-wide blocker.

#### Scenario: Terminal frame failures remain visible
- **WHEN** every selected frame Work is terminal but some have no usable output
- **THEN** progress may reflect their terminality under the current contract, while actual preparation fulfillment preserves those failures and cannot report them as acquired frames

#### Scenario: Faster extraction omits promised metadata
- **WHEN** an implementation improves timing by omitting photography fields required by the effective current metadata profile
- **THEN** preparation acceptance fails even if the narrower microbenchmark is faster and every requested internal call returned

### Requirement: Video preparation respects actual frame availability
For selected video preparation, the implementation SHALL resolve its finite temporal sampling intent against decodable frame availability with explicit source/profile limitations. It MUST NOT assume that container duration itself is a decodable frame position, fabricate distinct coverage from repeated copies of one frame, or classify a demonstrably invalid sampling choice as media corruption. Genuine source or decoder limitations SHALL remain localized and distinct from unexpected implementation failures. The exact discovery, seeking and decoding method SHALL remain replaceable.

#### Scenario: Sparse timeline ends before container duration
- **WHEN** a video has frame PTS values 0, 4.1041 and 8.2082 seconds and container duration 12.3123 seconds, and the selected example profile asks for bounded beginning/middle/end material
- **THEN** preparation uses valid available frames to fulfill that intent or reports a real scoped limitation, without requesting an empty endpoint and counting that as a corrupted video

#### Scenario: Only one frame is available
- **WHEN** the source can provide only one distinct frame
- **THEN** it is delivered with its actual position and limitation, and repeated references do not inflate unique-frame coverage

#### Scenario: One source is genuinely unreadable
- **WHEN** a truncated container has no readable video stream while other selected videos are valid
- **THEN** the source failure is accounted locally and valid siblings retain their successful outputs and reuse paths

### Requirement: Independent subject outcomes permit bounded shared execution
The implementation SHALL preserve subject-local identity, dependencies, provenance, success, failure and invalidation while allowing bounded provider batches, decoder reuse and coordinated database operations. Ephemeral batch membership, queue order or scheduling changes MUST NOT become semantic identity when they do not change the evidence or its validity. Shared physical execution MUST NOT erase an independently committed success or turn a single failed input into an unaccounted batch-wide outcome.

#### Scenario: A mixed batch contains one bad input
- **WHEN** a shared metadata or video operation can identify successful subjects and one failing subject
- **THEN** successes remain committed and reusable, the bad subject has its own outcome, and retry does not blindly repeat all previously successful subjects

#### Scenario: Concurrency changes without semantic changes
- **WHEN** only scheduling or batch organization changes and all semantic dependencies and validity observations remain equivalent
- **THEN** previously valid subject Work and Artifacts remain eligible for reuse rather than being invalidated solely by their former batch membership

#### Scenario: A shared worker is interrupted
- **WHEN** an execution owner disappears after some subject outcomes were committed
- **THEN** existing ownership/recovery rules recover only unresolved work and preserve those successes without introducing a persistent batch authority

### Requirement: Resource guarantees are backed by observable mechanisms
PreCheck SHALL apply and retain effective resource constraints using existing Run configuration and admission mechanisms. Declared process, concurrency or thread limits SHALL be enforced where claimed. Estimated memory demands, observed peaks and enforceable hard limits SHALL be distinguished. Status SHALL preserve existing honest lifecycle semantics rather than inventing a waiting state for unexplained resource or implementation failure.

#### Scenario: Decoder memory exceeds its admission estimate
- **WHEN** observed decoder memory materially exceeds the estimate used to admit work
- **THEN** that estimate is not reported as proof of an enforced memory ceiling, and resource certification requires correction or an explicit limitation before a broader concurrency claim

#### Scenario: More local parallelism is selected
- **WHEN** a replacement metadata method uses several long-lived processes
- **THEN** the admitted work remains within the applicable CPU, I/O, process and memory policy, while recorded subject outcomes and cancellation semantics remain intact

### Requirement: Operating-quality release claims require joint acceptance evidence
A release claim for PreCheck preparation quality or efficiency SHALL be backed by acceptance conditions fixed before product implementation for declared inputs, versions, effective preparation profile and resource conditions. Evidence SHALL cover valid output/coverage, first computation, reuse and relevant localized-change/failure behavior, plus the shipped composition at the claimed boundary. Same-work comparisons and default-policy comparisons SHALL be distinguished. Failed or omitted work MUST NOT be counted as throughput success, and new guarantees MUST NOT exempt their coordination cost from measurement.

#### Scenario: Reduced sample count lowers total runtime
- **WHEN** a candidate produces fewer frames or different fidelity under a different default policy
- **THEN** the comparison reports those differences and checks the approved preparation target before describing the lower wall time as an improvement

#### Scenario: Extraction improves but persisted preparation remains slow
- **WHEN** the extraction microbenchmark passes while coordination or reuse misses the approved full-producer budget
- **THEN** the release cannot claim that the full preparation performance target passed

#### Scenario: A generated scale test passes
- **WHEN** a generated million-row planning test succeeds without real media decoding
- **THEN** certification remains limited to that coordination boundary and does not certify original-video, storage or model throughput

#### Scenario: Component tests pass without installed execution
- **WHEN** individual producers pass but the release composition has not exercised the required Run/Read delivery path
- **THEN** the component evidence is retained but the corresponding installed product gate remains unproven
