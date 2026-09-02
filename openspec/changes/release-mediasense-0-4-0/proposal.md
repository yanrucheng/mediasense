## Why

The PreCheck scope-review change breaks the public `mediasense.precheck.run`
contract and raises the PreCheck store schema from 16 to 17. Shipping those
changes under `0.3.0` or as a patch would contradict MediaSense's pre-1.0
versioning contract and leave installed Skills and upgrade guidance mismatched.

MediaSense needs one reproducible `0.4.0` release and local upgrade path that
replaces the machine CLI, synchronizes the Human-selected Honeycomb's Skills,
and leaves older Dataset workspaces untouched and honestly incompatible.

## What Changes

- **BREAKING**: release MediaSense `0.4.0` with the new PreCheck Run contract
  digest and PreCheck store schema 17; keep the Dataset manifest, Plan, Geo, and
  Apply store versions unchanged.
- Update all current-version, compatibility-matrix, installation, upgrade, and
  rollback guidance from the `0.3.x` release line to `0.4.x`.
- Add an explicit `mediasense skills upgrade --target <honeycomb-skills>` command
  that atomically replaces only the four packaged MediaSense Skill directories,
  preserves unrelated Skills, and retains a recoverable backup until the whole
  matched set is installed.
- Keep `skills install` non-overwriting for first installation and ambiguity.
- Document that schema-16 Dataset workspaces are preserved but unsupported by
  `0.4.x`; users create a new schema-17 workspace instead of receiving an
  implicit migration or compatibility shim.
- Build, inspect, and clean-install the exact `0.4.0` wheel, then replace the
  local uv tool and verify Skill installation against an explicit temporary
  Honeycomb. Keep the MediaSense source checkout unactivated unless a Human
  separately selects it for operational work. Do not run the Hong Kong fixture.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mediasense-versioning`: Declare the `0.4.x` compatibility combination and
  the schema-16-to-17 clean-start/rollback boundary.
- `mediasense-distribution`: Add a bounded, explicit release-matched Skill
  upgrade operation and `0.4.0` installation verification.

## Impact

- Package metadata, runtime version output, Skill compatibility text, README and
  installation guidance.
- Dataset/Open mocks and compatibility documentation for PreCheck store 17.
- CLI and runtime Skill installation code plus focused conflict, atomicity, and
  unrelated-content preservation tests.
- Wheel build, isolated clean-install probes, local `uv tool` replacement, and
  explicit temporary-Honeycomb Skill verification.
- No source-media mutation, Dataset workspace migration, user-wide Agent
  configuration edit, optional-model download, provider call, or Hong Kong
  fixture execution.
