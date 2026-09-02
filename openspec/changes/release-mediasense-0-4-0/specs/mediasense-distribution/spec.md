## ADDED Requirements

### Requirement: Packaged MediaSense Skills upgrade as one matched set
The CLI SHALL expose `mediasense skills upgrade --target <path>` for an explicit
existing Skill root. It SHALL stage and replace only the packaged MediaSense
Skill directories, preserve unrelated entries, report installed, upgraded, and
unchanged names, and restore every touched MediaSense directory if the matched
set cannot be completed.

#### Scenario: 0.3 Skills are upgraded to 0.4
- **WHEN** the explicit target contains a differing prior MediaSense Skill set and writable stable storage
- **THEN** the operation installs the complete packaged `0.4.x` set, reports every installed or upgraded name, and leaves unrelated Skills byte-identical

#### Scenario: Mid-upgrade failure occurs
- **WHEN** replacement fails after at least one MediaSense Skill was moved or installed
- **THEN** the operation restores all pre-operation MediaSense Skill contents, removes its staging state, and reports failure without claiming the target is upgraded

#### Scenario: Existing set already matches
- **WHEN** all four target Skill directories are byte-identical to the packaged release
- **THEN** the operation reports all four as unchanged and performs no replacement

### Requirement: Exact 0.4.0 wheel drives local installation evidence
The release SHALL build and inspect one exact `0.4.0` wheel, verify it in an
isolated installation, and use that same artifact for the authorized local uv
tool replacement.

#### Scenario: Exact wheel is installed locally
- **WHEN** the verified `mediasense-0.4.0-py3-none-any.whl` replaces the existing uv tool
- **THEN** an absolute-path subprocess reports `0.4.0`, exposes all seven Tools with the expected contract digests, and finds the complete packaged Skill set

### Requirement: Source checkout is not an implicit Honeycomb
The release SHALL keep packaged Skill sources separate from Agent-client Skill
discovery paths and SHALL NOT require the MediaSense source checkout to activate
its own Skills or MCP server. Skill installation evidence SHALL use an explicit
operational or temporary Honeycomb target.

#### Scenario: Release is developed and installed from its source checkout
- **WHEN** MediaSense is built or its machine CLI is installed from the source checkout without the Human selecting that checkout as an operational Honeycomb
- **THEN** the checkout contains no repository-provided `.agents/skills/mediasense*` activation and no project MCP registration is created

#### Scenario: Packaged Skills are verified
- **WHEN** release verification exercises Skill installation or upgrade
- **THEN** it uses an explicit temporary Honeycomb and leaves the source checkout's Agent-client activation state unchanged
