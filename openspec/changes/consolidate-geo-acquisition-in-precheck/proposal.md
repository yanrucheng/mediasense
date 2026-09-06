# Proposal: Restore Compressed PreCheck Geo Acquisition Through the Shared Tool

## Why

Two corrections to the 0.7.1 flow each fixed only one side of the contract. The
first queried Geo for a small representative set but left many located Source
Items without a Result outcome. The second covered every located Source Item by
turning nearly every interpolated coordinate into a query, bypassing the media,
time, trajectory, and bundle relationships PreCheck had already computed.

The durable boundary is neither “one representative per bundle” nor “one query
per photo.” PreCheck must produce one outcome per located Source Item while
sharing external observations only where local evidence supports it. Geographic
lookup itself remains a stage-neutral capability: PreCheck is its normal bulk
caller, and a Plan Agent may call it directly for bounded investigation when it
challenges prepared evidence.

## What Changes

- Restore the public `mediasense.geo.query` Tool, provider-neutral capability,
  Dataset Geo journal, MCP discovery, and trusted Human authorization flow.
- Make PreCheck form Geo acquisition units after bundle construction. A bundle is
  only a candidate scope: consistent same-asset and stationary members may share
  one observation, while movement, coordinate/datum conflict, missing temporal
  support, or excessive span splits the scope. Adaptive visual compression does
  not directly define Geo equivalence.
- Keep all Source Items with a final coordinate in the coverage set and project a
  separate reverse-geocode outcome to each item, even when several items reuse one
  external observation.
- Keep exact-coordinate deduplication as the last request-layer defense. Spatial
  tolerances remain a versioned, replaceable PreCheck method rather than a public
  product invariant.
- Make Geo observation Work identity independent of batch order and Source Item
  membership. Preserve compatible successful 0.7.1 observations through an
  explicit local compatibility path.
- Bind PreCheck confirmation to the shared Geo Tool's exact pending request and
  effect envelope. The Tool enforces the batch-level provider-request ceiling and
  journals admitted effects before network execution.
- Keep Plan's ordinary contract focused on per-item Result facts. When a material
  Plan judgment needs narrower place evidence, the Agent may issue a separate,
  explicitly authorized `mediasense.geo.query`; it does not mutate the Result or
  repair missing PreCheck coverage.
- Preserve old immutable Results as historical bytes. Migrate the public Dataset
  manifest forward to declare the restored Geo journal store without rewriting
  PreCheck or Plan databases.

## Capabilities

### Modified Capabilities

- `geo-capability`: retain the stage-neutral public Tool, exact authorization,
  bounded routing, request accounting, and idempotent effect journal.
- `precheck-confirmed-geocoding`: separate coverage, acquisition-unit formation,
  provider query, and per-item projection.
- `precheck-run-orchestration`: pass completed bundle evidence into Geo acquisition
  and gate publication on complete per-item outcomes.
- `precheck-agent-workflow`: explain compressed query counts, cache reuse, hard
  request ceilings, and Result handoff.
- `plan-agent-workflow`: permit bounded direct Geo investigation while forbidding
  it from becoming a repair path or second Result authority.
- `tool-host`: expose one shared Geo Tool and supply trusted MCP authorization.
- `dataset-workspace`: restore the independently versioned Geo journal store.
- `mediasense-distribution`: package the Geo Tool contract and advertise seven
  public Tools.

## Impact

- Production PreCheck uses the shared Geo Tool instead of a private provider
  engine.
- On the paused Hong Kong Run, read-only evaluation changes the prospective query
  set from 1,611 exact coordinates to 225 conservative acquisition queries while
  retaining all 1,838 located Source Items. No Provider request was made.
- Input reordering no longer changes observation Work identity or later query
  routing. All 144 historical successful observations pass the explicit
  coordinate/profile/language compatibility check; 98 of them are selected by
  the current compressed query set, leaving 127 pending queries and a 254-request
  hard ceiling with both current adapters.
- The Dataset manifest advances to version 3 and declares the Geo journal at
  version 1; supported version 1 and version 2 manifests migrate atomically.
- Tests and documentation distinguish Source Item outcomes, logical queries,
  cache reuse, provider requests, and hard authorized ceilings.
