## MODIFIED Requirements

### Requirement: PreCheck remains local-first with one bounded online exception
The Skill SHALL state that external work is disabled until exact Run authority is
present and SHALL recognize only the trusted confirmation contract for reverse
geocoding a normalized, deduplicated coordinate set frozen after compression.
It SHALL NOT describe the product as having an `offline` mode or describe required
Geo acquisition as optional when the frozen batch is non-empty.

#### Scenario: Frozen reverse-geocode set needs authorization
- **WHEN** the Tool pauses with a frozen reverse-geocode disclosure
- **THEN** the Agent presents the exact coordinates and logical-query count, transmitted data classes, provider/request/cost ceilings, Result retention, and each known or unknown provider policy before obtaining trusted Human confirmation bound to the disclosure identity

#### Scenario: Human declines reverse geocoding
- **WHEN** the Human declines the frozen disclosure
- **THEN** the Agent submits `decline`, reports terminal non-success with zero provider requests, and does not hand a Result to Plan

#### Scenario: Provider is unavailable
- **WHEN** the Run terminates with `provider_unavailable`
- **THEN** the Agent explains that provider configuration must change before a successor Run and does not describe the condition as refusal or missing authorization

### Requirement: Result axes govern handoff and escalation
The Skill SHALL interpret coverage, readiness, integrity, and the deterministic
Geo acquisition summary independently and SHALL hand Plan only an exact immutable
Result reference whose required acquisition is `complete` or `not_applicable` and
whose material limitations are explicit.

#### Scenario: Result is partial but Plan-ready
- **WHEN** `mediasense.precheck.read` reports partial coverage, `plan_ready` readiness, valid integrity, and complete or not-applicable Geo acquisition
- **THEN** the Agent may offer the exact `result_ref` to Plan together with material qualifications and omissions

#### Scenario: Historical readiness omits Geo acquisition
- **WHEN** an old Result says `plan_ready` but `geo_summary` reports `incomplete`
- **THEN** the Agent requires a successor PreCheck Run and does not hand that Result to Plan

#### Scenario: Result is blocked
- **WHEN** `mediasense.precheck.read` reports blocked readiness
- **THEN** the Agent explains the blocking evidence and asks the Human to choose a successor Run, a supported rebuild, or retaining the Result and stopping without claiming Plan readiness

#### Scenario: Result is ready for Plan
- **WHEN** the Human proceeds with a valid Plan-ready Result whose required Geo acquisition is closed
- **THEN** the Agent hands Plan the exact `result_ref` and directs all later PreCheck fact and Evidence access through `mediasense.precheck.read`

