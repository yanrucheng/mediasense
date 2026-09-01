---
id: "01-result-mediasense"
title: "MediaSense Installation and Versioning Result"
type: delegation
status: draft
created: 2026-08-30
updated: 2026-08-31
timezone: "Asia/Shanghai"
parent: "td-260830-2227-mediasense-distribution"
depends-on:
  - "01-request-mediasense"
superseded-by: ""
---

# MediaSense Installation and Versioning Result

## Implementation status and acceptance correction

MediaSense 0.2.0 now has a complete local-product entry path rather than requiring
users or Agent clients to assemble repository Python classes. The implemented scope
includes an installable wheel and executable, portable-first Dataset onboarding,
one composition root, a stdio MCP Tool Host, packaged Skills, diagnostics,
version/store compatibility checks, upgrade and rollback guidance, and isolated
clean-install verification.

The earlier acceptance conclusion is withdrawn. A real first-use run on 2026-08-31
showed that `mediasense.dataset.open` registered the public `dataset_ref` as an
internal `dataset_id`, so the immediately following `mediasense.precheck.run`
`start` returned `dataset_not_found`. The earlier subprocess and installed-wheel
smokes exercised only `precheck.run status` and therefore did not establish the
claimed first-use path. The archived OpenSpec record remains historical evidence,
not current acceptance evidence. Overall acceptance and delegation closure remain
pending explicit user confirmation after this correction.

## Local Honeycomb follow-up — not yet user-accepted

The installation scope recorded below was also found to be too broad. The current
authority is the archived OpenSpec change
`2026-08-31-adopt-local-honeycomb-integration` together with
`/Users/chengyanru/repos/personal/mediasense/readme/agent-integration.md`:

- the `mediasense` CLI may be installed machine-wide;
- Skills belong by default under the Human-selected Honeycomb's
  `.agents/skills/` directory;
- the Codex MCP registration belongs in that Honeycomb's
  `.codex/config.toml` and starts `mediasense mcp` for a session; and
- the Dataset workspace is independent from all three.

The old user-level commands retained later in this result are historical evidence
only and must not be followed as current setup instructions. This follow-up does
not reinstate overall product acceptance, close the delegation, or certify any
non-Codex client. A fresh project-in/project-out Codex comparison and renewed Human
acceptance are still required.

The review-blocker correction now assigns the compatible release identity
`0.3.0`. The prior global `0.2.0` uv tool was replaced by the exact locally built
`0.3.0` wheel, and an absolute-path probe outside repository command resolution
completed seven-Tool discovery and
`mediasense.dataset.open → mediasense.precheck.run start`. This is corrective
evidence, not renewed Human acceptance; the delegation remains active.

## User experience delivered

### Install and verify

From a trusted checkout, the reviewable installer is:

```bash
/Users/chengyanru/repos/personal/mediasense/scripts/install.sh
mediasense --version
mediasense doctor
```

An exact release artifact can also be installed with:

```bash
uv tool install /private/tmp/mediasense-release-final-6xyCpH/mediasense-0.2.0-py3-none-any.whl
```

The installer delegates to `uv tool install`. It does not silently install `uv`,
system packages, optional models, or Agent configuration. `--offline` prohibits
dependency downloads; `--force` is required to replace an existing MediaSense
tool environment. `doctor` reports required failures and optional ExifTool,
FFmpeg/ffprobe, local-model, filesystem, resource, configuration, and offline
capabilities without installing anything or making network calls.

The complete installation and lifecycle guide is:

`/Users/chengyanru/repos/personal/mediasense/readme/installation.md`

### Open a Dataset without a separate init step

The first meaningful command is the source itself:

```bash
mediasense dataset open /Volumes/PhotoDisk/Photos
```

MediaSense selects the Dataset workspace in the accepted order:

1. a user-supplied `--workspace` path;
2. `<external-volume>/.mediasense/datasets/` when the source is on an eligible
   external volume; and
3. the platform-local application-data directory, which is
   `~/Library/Application Support/MediaSense/datasets/` on macOS.

This keeps the databases, derived evidence, Results, Plans, journals, and Receipts
with a large external Dataset, so an overnight PreCheck does not need to be
repeated merely because the drive is connected at a different mount path or used
from another compatible machine. The media directory itself remains read-only;
portable state lives under the volume-level `.mediasense/datasets/` directory,
not inside the media tree.

Every successful open prints the exact source, `dataset_ref`, selected workspace,
selection tier, effective non-secret configuration sources, offline policy,
manifest version, and component store versions. Explicit-path errors, corrupt or
incompatible higher-priority state, ambiguous matches, unsafe nesting, and
unsupported filesystem capabilities fail visibly instead of silently falling
back. Compatible relocation is audited; an identity mismatch blocks reuse, and
operator-confirmed rebinding starts a new reuse domain.

The permanent Tool authority is:

`/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260831-0009-dataset-open/index.md`

### Historical Agent connection (superseded)

The following commands record the 2026-08-30 installation approach. They were
superseded on 2026-08-31 because both commands create user-wide discovery rather
than the required Honeycomb-local scope. Do not use them as current guidance.

MediaSense starts a local stdio MCP server on demand:

```bash
mediasense mcp
```

It is not a daemon and opens no network port. Agent-client registration remains
owned by the client. For Codex:

```bash
codex mcp add mediasense -- mediasense mcp
mediasense skills install --target ~/.codex/skills
```

MediaSense refuses to overwrite a different existing Skill and treats an
identical installation as idempotent. The complete integration guide is:

`/Users/chengyanru/repos/personal/mediasense/readme/agent-integration.md`

Under the replacement local setup, the intended first conversation can still be
as simple as:

```text
Prepare /Volumes/PhotoDisk/Photos with MediaSense. Keep the source read-only and
do not use network providers.
```

The Agent opens the Dataset first, reports which configuration and workspace were
selected, then hands the exact returned `dataset_ref` to PreCheck. The installed
PreCheck, Plan, and Apply Skills preserve the existing human confirmation and
stage boundaries.

## Product surfaces implemented

### Distribution and Human-facing CLI

- `mediasense` is an installed executable backed by package metadata from one
  authoritative version source.
- The control surface includes help, version, Dataset open/inspect, doctor, Tool
  list/show/call, Skill path/install, and MCP startup.
- Wheel and sdist resources include the public contracts, one product entry Skill,
  and all three stage Skills;
  parity tests compare them byte-for-byte with repository authorities.
- Installation, first use, Agent connection, upgrade, rollback, uninstall,
  cleanup, and troubleshooting are documented under
  `/Users/chengyanru/repos/personal/mediasense/readme/`.

### Composition root and Tool Host

One Dataset-bound composition root constructs configuration, packaged schemas,
stores, providers, Dataset resolution, and the accepted Tool set. Transport code
does not redefine business requests. Confirmation and authorization information
is carried in a transport-only envelope, and external providers remain disabled
by default.

The Host exposes seven Tools:

1. `mediasense.dataset.open`
2. `mediasense.precheck.run`
3. `mediasense.precheck.read`
4. `mediasense.plan.work`
5. `mediasense.geo.query`
6. `mediasense.apply.run`
7. `mediasense.apply.read`

The first six pre-existing stage Tools remain semantically unchanged; Dataset
Open is the new stage-neutral onboarding Tool. The real subprocess regression now
performs MCP initialization, Tool discovery, Dataset open, and an actual PreCheck
start. The earlier status-only check remains as separate negative lookup coverage.

### Version and persistence policy

The application version is `0.2.0` and follows SemVer before 1.0: minor versions
may contain documented breaking CLI, Host, manifest, or store changes; patch
versions are compatible fixes. Package metadata, `mediasense --version`, artifact
names, and `/Users/chengyanru/repos/personal/mediasense/CHANGELOG.md` agree on the
same version.

Application, Tool contract, Dataset manifest, component stores, packaged Skills,
and computation validity are versioned independently. The supported initial
matrix is:

| Surface | Supported value |
| --- | --- |
| Application | `0.2.x` |
| Dataset manifest | `1` |
| PreCheck store | `15` |
| Plan store | `2` |
| Geo journal | `1` |
| Apply store | `2` |
| Packaged Skills | From the same MediaSense release |

Public Tool contracts have stable identities and exact schema digests. Dataset
opening rejects corrupt, unversioned, unsupported-newer, or otherwise incompatible
installed state before mutation. Future supported migrations have an explicit
preflight, journal, backup, apply, verify, and rollback boundary, but 0.2.0 does
not add speculative migrations. An application upgrade alone is not a blanket
PreCheck invalidation key; only inputs and producer conditions that change result
meaning invalidate reusable Work.

## Historical installation evidence and correction

The earlier verification was performed on 2026-08-31 in the shared macOS worktree while
preserving all pre-existing and concurrent uncommitted work.

The final artifacts were built successfully at:

- `/private/tmp/mediasense-release-final-6xyCpH/mediasense-0.2.0-py3-none-any.whl`
- `/private/tmp/mediasense-release-final-6xyCpH/mediasense-0.2.0.tar.gz`

The wheel was installed into a fresh temporary Python 3.11 environment independent
of the repository `.venv`. The offline smoke test verified wheel metadata and the
entry point, version and doctor output, seven-Tool discovery, first and repeated
Dataset open, installation of all three Skills, a real subprocess MCP initialize
and `tools/list`, a non-destructive `mediasense.precheck.run` status call,
uninstallation of the executable, and retention of Dataset state. It ended with
`distribution smoke: ok`. The reviewable installer also completed offline, and a
second identical invocation completed idempotently.

That result was insufficient evidence for first use: neither the repository stdio
test nor the installed-wheel smoke called `mediasense.precheck.run` with
`action: start`. Consequently, the historical `distribution smoke: ok`, the
status-only MCP result, and the prior overall-acceptance statement must not be
used as proof that the main flow worked.

Historical gates (not evidence that the first-use start path worked):

- Python 3.11 non-live suite: `518 passed, 12 deselected`.
- Ruff: passed.
- OpenSpec strict validation before archive: 12 passed, 0 failed.
- Documentation validation: 63 Markdown files, with zero frontmatter, folder
  index, index-entry, or local-link errors.
- All three packaged Skills: passed their validator.
- Final wheel and sdist build: passed.
- Offline clean-install smoke: passed.
- `uv lock --check`, installer shell syntax, and `git diff --check`: passed.

After archival synchronization, the packaged-resource parity test passed, strict
OpenSpec validation passed for all 15 remaining specs/active changes, and the
expanded documentation set passed frontmatter, folder-index, index-entry, and
local-link validation across 64 Markdown files. Ruff, lock, installer syntax, and
`git diff --check` also remained clean.

Corrective implementation verification on 2026-08-31 added RuntimeHost, stdio MCP,
legacy-workspace, and clean-installed-wheel coverage for the actual
`dataset.open -> precheck.run start` path. The non-live suite passed with 523 tests
and 12 deselections; Ruff, all 15 strict OpenSpec validations, and
`git diff --check` also passed. These results verify this correction but do not
reinstate overall acceptance without a new explicit user decision.

The corrective wheel was built at
`/private/tmp/mediasense-dataset-id-wheel-final.2UX1XH/mediasense-0.2.0-py3-none-any.whl`.
It was installed into an isolated `uv tool` environment, exercised through the
installed `mediasense mcp` executable, and uninstalled after the real
`dataset.open -> precheck.run start` check returned a valid Run reference.

The detailed evidence moved with the archived OpenSpec change to:

`/Users/chengyanru/repos/personal/mediasense/openspec/changes/archive/2026-08-30-productize-mediasense-distribution/verification.md`

## AI Album migration judgment

AI Album was used only as historical evidence. It is not a runtime dependency or
design authority.

- Runnable installation changed intentionally from Docker/repository-oriented
  invocation to an installable Python wheel and executable.
- Keeping Dataset-derived state with the mounted Dataset is preserved, while the
  mechanism intentionally changes from path-oriented `.similarity_cache` state to
  a volume-level Dataset workspace with manifest and source identity.
- Cross-machine reuse, MCP Tool discovery, and integrated store/contract version
  checks are intentional improvements or newly comparable capabilities.
- Existing durable PreCheck Run, Work, Result, and dependency-specific reuse
  remain available behind the installed composition root.
- The changed directory layout is not a regression: it retains portable reuse
  while avoiding writes inside the media root and adds identity checks,
  recoverable diagnostics, and version safety.

The full comparison is:

`/Users/chengyanru/repos/personal/mediasense/openspec/changes/archive/2026-08-30-productize-mediasense-distribution/migration-comparison.md`

## Recorded limitations

- macOS is the first product-certified platform. Linux package execution may
  work, but removable-volume and Apply filesystem behavior are not certified;
  Windows is unsupported.
- External-volume precedence and changed-mount-path behavior were tested with
  isolated filesystem simulations, including deterministic Darwin Volume UUID
  parsing. No physical removable-volume or second-machine run was performed.
- No live map provider, paid API, local-model suite, fresh Hong Kong replay, real
  media move, package publication, or release was performed.
- Codex has the documented complete Skill-guided integration. Other stdio MCP
  clients are protocol-compatible but not yet product-certified.
- The final artifacts are local acceptance artifacts in `/private/tmp`, not a
  published distribution channel.

## Boundaries left unchanged

- Source media remains read-only during PreCheck, remote and billable providers
  remain disabled by default, and long work stays observable and resumable.
- Plan continues to own interpretation and user interaction; source media is not
  reorganized during Plan.
- Apply still accepts only a Frozen Plan and retains deterministic safety gates,
  collision refusal, same-filesystem checks, journaling, idempotency, and
  post-verification.
- No commit, merge, push, package publication, release creation, real-media
  mutation, AI Album modification, fixture modification, or delegation closure
  was performed.

Archiving records the historical work state, including the now-superseded
status-only evidence. Comprehensive integration acceptance, merge, publication,
release, and delegation closure remain decisions for the user or originating
workline.
