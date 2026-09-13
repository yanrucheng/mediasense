## Status and evidence boundary

This file owns the implementation acceptance criteria and evidence. The design-only planning milestone on 2026-09-13 withdrew prematurely written code; the Human subsequently explicitly authorized formal development and isolated acceptance. Daily installation and publishing are outside that authorization. Planning evidence below remains historical and never substitutes for the implementation record.

## Development-ready gate

| Gate | Required evidence |
| --- | --- |
| Concepts and decisions | Accepted model linked once; local parameter semantics and complete explicit requests have no unresolved alternatives |
| Contract design | Proposed fields, required/optional/null meanings, scope binding and failure outcomes are explicit in design/specs; actual canonical schema edits are assigned to implementation |
| Consumer usability | The planned read→request→new Result→correspondence→Plan sequence does not require private state |
| Negative behavior | Incomplete Profiles, scope overlap/outside/empty, stale configuration, wrong Result/cursor and false correspondence have specified outcomes |
| Engineering design | Configuration projection, dependency boundary, partitioning, sealed input lineage, recovery and retention are assigned to existing owners |
| Execution plan | Every implementation task has concrete files, prerequisites and an exit gate; all implementation tasks remain unstarted |
| Handoff boundary | Provide this design package and stop; the user arranges the implementation Agent |

Only OpenSpec document validation belongs to this planning milestone:

```sh
rtk proxy env OPENSPEC_TELEMETRY=0 openspec validate simplify-precheck-run-composition --strict --no-interactive
```

The implementation Agent must first create and validate the canonical schemas, shared fragments and positive/negative examples, including configuration identity vectors. It then implements the matrix below with real components. No executable verifier or test has been retained from this planning task.

## Implementation acceptance matrix

| Case | Pass condition |
| --- | --- |
| Ordinary same-input Run | Different request_id creates a new Run/Result; valid expensive metadata/decoding/embedding/detector/provider work is not executed again |
| Exact replay and resume | Replaying an accepted request after Dataset defaults change still returns its Run; resume keeps the frozen settings; changed request content conflicts |
| Local threshold change | T uses its full new settings; S−T parameters are identical to their declaration; cached inputs are reused; every accounted item remains present |
| Existing group crosses T | Inputs are split through exact source members before final compression; one representative's attributes never become facts about the other members |
| Count fallback / actual dependency | Outside groups may change, with readable members/basis; unchanged dependencies do not cause gratuitous producer execution |
| Missing selected input | Only the selected/actually required boundary input is prepared; disabled content comparison rejects an ineffective content-threshold override; missing enabled backend follows a real recoverable prerequisite |
| Same bytes in different files | Two source occurrences map to two distinct target references; path/content equality without an explicit input binding gives unproven |
| Changed / unavailable source | Detected revision change fails the same-snapshot request; disconnection is a recoverable availability condition; neither is silently accepted as the old input |
| Different / historical Result | Read is usable; absent preparation is null with a qualification; absent direct lineage is unproven, without private Work lookup |
| Large scope readback | An override containing 100000 synthetic source references reads back as one profile_scope selector; resolve pages all exact members with stable identities and no configuration truncation |
| Source Set cursor | Changing source Result, target Result, expression, limit or position invalidates the cursor; full original membership digest remains independently recomputable |
| Disabled capability | Cached disabled detector/embedding output does not become newly requested evidence; independent valid caches remain reusable |
| Failure / publication retry | Inject failure before and after durable publication boundaries; retry neither duplicates Result publication nor loses valid sibling work |
| Retention | Old Result bytes/reads remain stable after new Runs and producer-cache cleanup; protected publication material is retained or loss is explicitly reported |
| Plan continuation | Public Tools can recover prior notes/preferences and map the intended source scope into a new Work; new Evidence is inspected where material; new Human confirmation is required |
| Host and installed artifact | The same path executes through real composed internals and isolated CLI/MCP; tool discovery and mock success alone do not count |

## Cost measurement and acceptance

Use controlled synthetic preparation inputs of 4096 and 8192 entries plus the small eight-entry boundary case. First measure the existing baseline under the same build, hardware, source-verification profile, resource limits and output obligation. Use warmed repeated runs and report median wall time separately for verification, reusable-work lookup, actual producer execution and sealing. Do not manufacture a universal seconds threshold.

Mechanistic requirements are fixed before measurement: zero expensive producer calls for fully valid warm inputs; threshold-only changes do not rerun metadata/decoding/embedding whose dependencies are unchanged; a newly demanded uncached source does not invalidate unrelated Work; input visits, persisted membership and Result assembly remain linear in the accounted sources plus relationships. Record query/write counts and peak memory so a nominal cache hit cannot hide quadratic coordination or per-Run duplication of large producer outputs.

A failure of these mechanisms blocks release. Unexpected dominating full-source I/O or materially increased resource cost requires an explicit optimization/acceptance decision, not a weaker output or an invented timing claim. Existing historical 62-test evidence is not this release's acceptance, and the old 500→3→200 scale test is not cited until its current contract calls run successfully.

## Verification record

2026-09-13: `openspec validate simplify-precheck-run-composition --strict --no-interactive` passed. This validates the OpenSpec document structure only. This task's schema/contract edits, executable validator and tests were withdrawn; targeted diff inspection confirmed no remaining changes in the Run/Read contracts, their packaged schemas or the existing Run contract test from this task. Concurrent Plan development was preserved. No schema/runtime test or production acceptance is claimed.
