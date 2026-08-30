## Why

MediaSense defines PreCheck, Plan, and Apply as three user-facing stages, but the
repository exposes Skills only for Plan and Apply. The missing PreCheck Skill
leaves Agents without durable guidance for goal-driven compression, observable
long-running work, bounded external confirmation, honest partial Results, and
the exact handoff to Plan even though the Run and Read contracts are complete.

## What Changes

- Add a normally discoverable repository-local `mediasense-precheck` Skill.
- Define the Agent workflow for choosing a compression purpose, operating and
  recovering a PreCheck Run through its Tool boundary, interpreting immutable
  Results, and handing one exact `result_ref` to Plan.
- Preserve local-first execution and the single confirmed online exception for
  a frozen, deduplicated post-compression reverse-geocode query set.
- Add positive and negative activation checks plus independent, realistic Agent
  forward tests for compression revision, interruption, partial/blocked Results,
  and stage handoff.
- Do not change PreCheck Tool schemas, runtime algorithms, Result authority, or
  source-media safety behavior.

## Capabilities

### New Capabilities

- `precheck-agent-workflow`: User-facing Agent guidance for operating PreCheck
  through the existing Run and Read contracts without taking over Plan or Apply.

### Modified Capabilities

None.

## Impact

- Adds `.agents/skills/mediasense-precheck/` and focused Skill validation assets.
- Adds one OpenSpec capability governing the user-facing PreCheck workflow.
- Uses the existing `mediasense.precheck.run` and `mediasense.precheck.read`
  boundaries; no runtime API, persistence format, dependency, or media I/O is
  added or changed.
