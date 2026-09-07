## ADDED Requirements

### Requirement: The Geo Tool owns finite retry within exact authority
The shared Geo Tool SHALL own all automatic Provider retry for one admitted request. The effective retry profile SHALL be immutable, fingerprinted and included in upfront effect ceilings. Retry SHALL stop on cancellation, deadline, attempt or authority exhaustion, permanent error or indeterminate effect. PreCheck SHALL NOT repeatedly resubmit a terminal failed result as a new attempt.

#### Scenario: Transient failure recovers
- **WHEN** a transient error has remaining attempts, time and authorized effect budget
- **THEN** Tool retries internally with bounded cancellable delay and reports every actual request

#### Scenario: Attempt budget exhausted
- **WHEN** the finite retry profile has no admissible attempt remaining
- **THEN** it returns a terminal qualified failed component and replay does not retry it again

#### Scenario: Authority is smaller than the retry policy ceiling
- **WHEN** another Provider call would exceed accepted request or billable limits
- **THEN** that call is not sent and the local failure describes budget exhaustion

#### Scenario: Effective retry profile changes
- **WHEN** a caller retries an earlier identity under a different effective profile
- **THEN** existing journal identity and confirmation are not silently reused for changed effects

#### Scenario: No candidate is a completed lookup
- **WHEN** a Provider returns no_result without transient failure
- **THEN** the same Provider is not retried merely to seek a nonempty answer

#### Scenario: Provider effect is indeterminate
- **WHEN** the Tool cannot prove whether an effect completed
- **THEN** it stops automatic continuation and retains indeterminate rather than treating the uncertainty as a safely retryable failure
