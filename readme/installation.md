# Installation and upgrade runbook

This is the single authoring source for MediaSense installation, local upgrades,
readiness verification, and rollback. Its purpose is to make the selected release,
the actual executable, the project Skills, and the running Agent session agree,
while preserving Dataset state and the user's existing configuration.

The authoritative home is `readme/installation.md` in the MediaSense repository.
The product entry Skill carries an identical release snapshot at
`mediasense/references/installation.md` for use without a checkout or network.
Edit this source; [maintain the snapshot and checks](#maintaining-the-runbook) in
the same change. Repository paths below refer to the selected MediaSense checkout;
installed users can follow the workflow using a verified release and its evidence.
README, AGENTS, and the integration guide point here. Historical release records
prove what happened for that release; they do not define a second procedure.

The contributor changing distribution or integration owns keeping this procedure,
its commands, and its delivered snapshot correct. Application version comes from
`pyproject.toml`, persistent-format support from
`src/mediasense/runtime/versioning.py`, and Tool meaning from
`docs/spec/contract/`. This document does not maintain separate version declarations.

## Install

Follow the [workflow](#workflow). For Agent-guided first use, acquire the complete
`mediasense` entry-Skill directory, including its references, through the client's
normal local-Skill mechanism into a Human-selected operational Honeycomb. A Skill
cannot load itself. The loaded entry then follows this runbook and routes to the
owning stage. The same workflow also supports a direct CLI installation.

The source checkout, machine CLI, operational Honeycomb, and Dataset workspace
have independent purposes. The source checkout's packaged Skills are release
inputs, not an instruction to activate MediaSense in that checkout.

## Upgrade and rollback

Use the same [workflow](#workflow) with the existing targets and managers. Every
code or resource change after the installed build requires a new content check,
even when the version string has not changed. An upgrade is complete only at the
scope actually verified: package, machine installation, and Agent session are
separate claims. Recovery uses the [rollback conditions](#recovery-and-rollback).

For compatibility, consult the selected release's `CHANGELOG.md`, active contracts,
and format declarations. The 0.9 Read change uses `review.items` and one MCP
`structuredContent` result; old nested PreCheck requests remain unsupported.
The 0.10 Geo journal migration preserves retained evidence but excludes old Host
writers. No version number alone proves compatibility with a retained Dataset.

The continuous Plan view release uses private Plan store format 4. On a supported
v3 Dataset, it keeps the existing database filename, Work/Result/Plan references,
notes, preferences, cursor key, request history and Frozen Plan bytes. Nonempty
old candidates gain kind=candidate; absent candidates remain absent. It retains
a consistent pre-conversion database image beside the store and the preceding
Dataset manifest. New requests use the new interface; old request IDs cannot be
reinterpreted. It never invents reviewed_revision for earlier confirmations.

Before upgrading a retained Dataset, stop its writers and finish any pending v3
seal using the previous build. The new build refuses that unresolved publication
instead of guessing its outcome. Back up the whole Dataset consistently; verify
conversion and rollback on an isolated copy. Older Hosts reject format 4. A
rollback may restore the retained old snapshot only before new writes; otherwise
preserve the new state and use an explicitly verified recovery procedure.

The normal plan.work create/update/inspect/seal path now returns a local page
entry. The runtime starts a read-only loopback host on demand, verifies exact
build identity and keeps it available after the CLI exits. Idle heavy display
contexts are reclaimed after 1 hour (3,600 seconds; at most two globally); the process exits
after 72 hours (259,200 seconds) without effective use and with no in-flight content requests.
Background polling, health checks and a merely visible page do not renew use. Transient connection data
and diagnostics live below the selected user data home at runtime/plan-views;
only explicitly bound Dataset/Work/Result resources can be read. There is no
login service, remote hosting, media upload or HTTP planning/confirmation API.
Page projection remains disposable; authoritative planning remains in the Dataset.

Use the selected executable's `mediasense views status --json` to inspect its
actual build/process and `mediasense views stop --json` to stop it. Before replacing
an installation, stop the old build's page host with that exact executable and the
same MEDIASENSE_DATA_HOME used to start it, then verify actual exit. Status is
read-only and does not start/renew the service; unreachable with an owned lifetime
lock is unknown, not stopped. Stop closes admission, drains reads for at most five
seconds, and reports verified exit or an incomplete bounded verification. It does
not stop PreCheck, MCP, Agent or Apply processes. Pre-lifecycle builds do not gain
automatic exit until replaced; retire their identified host through their own
supported control, never by a process-name sweep. The next
ordinary Work inspect automatically restarts/rebinds the current build and returns
fresh URLs, without changing revision. A dead URL does not imply lost planning. Entries are stable per binding in one
process, and transient across restart; old links cannot wake a stopped process.
Diagnostics are exceptional recovery, not routine steps before/after each Plan.
The private activity POST only updates in-memory use time. Runtime logs rotate
at 1 MiB plus one backup; subsequent ordinary delivery best-effort removes known,
current-user diagnostic files of proven-stopped builds older than seven days.
Work, Result, Frozen Plan, prepared images, receipts and exported files are outside
this cleanup scope.
A ready descriptor does not prove all images are readable; inspect the reported
limits and actual page. Saving and display failures are separate.

The isolated delivery check is `tests/run_plan_preview_delivery_smoke.py`, run
with the isolated installation's Python and explicit --host, --output, --browser
and --playwright paths. It generates 1200 synthetic media, calls ordinary CLI and
MCP, and drives Chromium page controls. Keep output outside fixtures and Git.
Its synthetic acceptance context proves binding enforcement, not an actual Human
review or independent Agent's planning ability. Read the package-6 acceptance
record for the exact verified build and remaining scope.


## Workflow

These checkpoints fix required evidence and ordering where effects depend on it.
Investigation tools, test selection, and command orchestration may improve without
changing the checkpoints. Reuse evidence only when its exact build, environment,
and tested path still apply.

| Checkpoint | Evidence needed before continuing |
| --- | --- |
| 1. Locate | Actual executable/installer, selected project Skills/manager, MCP launcher, and affected Dataset formats |
| 2. Prepare | Exact source and wheel identity, dependency plan, matching resources, and recoverable previous installation |
| 3. Verify in isolation | Selected package and dependency combination execute the relevant shipped paths |
| 4. Switch | Existing authority covers the concrete changes; only the selected installation and project targets change |
| 5. Verify actual use | Actual executable, project resources, and newly loaded session match the selected release |
| 6. Record | Results, limits, and any remaining handoff are retained in the existing evidence home |

### 1. Locate the installation and intended scope

For an existing installation, begin with read-only inspection:

```bash
command -v mediasense
uv tool list
mediasense --version
mediasense doctor --json
mediasense tools list --json
```

Skip absent commands on a new machine. Resolve the executable and its interpreter;
inspect its installer receipt and package metadata to identify source, extras, and
actual dependency versions. For `uv tool`, the environment's `uv-receipt.toml`
records these installation inputs. Inspect package files when a build identity is
missing. A matching version or seven matching Tool names cannot prove matching
code, schema digests, or Skill references.

Locate the Human-selected Honeycomb independently of media and Dataset paths.
Identify the four actual MediaSense Skill directories, their manager and project
`skills-lock.json` if present. Include any applicable higher-scope copies that the
client might load; checking only a global directory can miss the operational copy.
Show unresolved target choices before writing; reuse explicit choices and
installation authorization already supplied in the session.

Parse the actual project's MCP registration and launcher. Record the resolved CLI,
working directory, and names/sources of needed environment settings without
printing credential values. A valid wrapper that loads credentials or proxy/CA
settings is an intentional configuration. Shell diagnostics do not establish what
the MCP child inherits. Record the user/Dataset configuration locations without
changing them.

For an upgrade that will access retained state, identify active Host writers and
inspect affected workspaces with `mediasense dataset inspect <absolute-workspace>`.
Use the release's format declarations and migration notes to decide compatibility
and backup needs. Do not open a live Dataset merely to test a migration.

### 2. Prepare one exact release and dependency plan

Use a trusted verified artifact, or build from an exact selected source revision.
For a local build, retain the commit and any deliberately included diff; build from
an isolated export so unrelated working-tree changes cannot slip into the package.
Use a new output directory for each candidate. Never overwrite a recorded wheel
and keep claiming its old checksum. A version and filename are insufficient;
retain the wheel SHA-256 and the source identity together.

Example for an already committed target, with placeholders replaced by actual
absolute paths and a full commit ID. Run the recipe in a shell that stops on errors
and pipeline failures:

```bash
set -euo pipefail
MS_REPOSITORY=/absolute/path/to/mediasense
MS_REVISION=full_selected_commit_id
MS_RELEASE=/absolute/path/to/new_retained_release_directory
MS_PYTHON=/absolute/path/to/existing/python
mkdir "$MS_RELEASE"
mkdir "$MS_RELEASE/source"
git -C "$MS_REPOSITORY" archive "$MS_REVISION" | tar -x -C "$MS_RELEASE/source"
uv build "$MS_RELEASE/source" --wheel --offline --no-python-downloads \
  --python "$MS_PYTHON" --out-dir "$MS_RELEASE/wheel"
```

Inspect wheel metadata, requirements, entry points, contracts, Skills, and this
runbook snapshot against that exact source. Select the single artifact explicitly
as `MS_WHEEL` and hash it with `shasum -a 256 "$MS_WHEEL"`. The artifact-only check
below rejects missing, extra, or different package files and a stale runbook:

```bash
"$MS_PYTHON" "$MS_RELEASE/source/tests/run_distribution_smoke.py" \
  "$MS_WHEEL" --verify-only
```

The artifact-only check uses Python's standard library and installs nothing.
An offline build/preparation failure means prerequisites remain unprepared.
Resolve downloads only within existing authorization, or disclose the specific
package sources and required change before requesting it. An existing approved
cache may be selected with `UV_CACHE_DIR`; an offline miss does not by itself
require a network download. Never silently drop `--offline`, fetch models, or
bootstrap a different Python.

Choose dependencies before switching:

- For a new installation, export runtime constraints from the selected source's
  `uv.lock`, including only the requested extras. For example:

  ```bash
  uv export --project "$MS_RELEASE/source" --locked --offline \
    --python "$MS_PYTHON" --no-python-downloads \
    --no-dev --no-emit-project --no-hashes --extra embeddings \
    --output-file "$MS_RELEASE/dependencies.txt"
  ```

  Omit `--extra embeddings` for the core package, or select `local-models` when
  needed. `--locked` must fail when the lock and project declaration disagree.
- For an upgrade, retain the existing Python, extras, and dependency versions
  wherever compatible. Record installed versions excluding MediaSense itself,
  compare them with target requirements, and form explicit constraints for the
  intended installation. Add new dependencies using the target lock; resolve
  necessary version changes in isolation and report the delta. Do not discard
  constraints just to make the resolver pass.

`uv tool install` does not consume a project's `uv.lock` automatically. Neither
`--offline` nor `--force` pins dependencies. Pass the reviewed constraints and the
exact wheel plus selected extras to both isolated and actual installation.
Retain the constraints, old artifact, installer receipt, and exact prior Skill/lock
content needed for rollback. Back up affected Dataset stores consistently before
any migration; copying a live SQLite file alone is not a consistent backup.

### 3. Verify the selected package in isolation

When building a release, run the default repository checks and tests material to
the changed paths against the selected source. A supplied verified release may
reuse its recorded source and packaging acceptance; an installer need not rebuild
it merely to repeat those checks. Exercise the actual wheel with the intended Python,
extras, and constraints, using temporary tool, configuration, and Dataset roots.
The existing distribution runner provides the bounded baseline. Choose
`MS_CHECK_PYTHON` from an existing development environment with `anyio` and `mcp`;
`--python` independently selects the intended installation interpreter:

```bash
MS_CHECK_PYTHON=/absolute/path/to/development/environment/bin/python
"$MS_CHECK_PYTHON" "$MS_RELEASE/source/tests/run_distribution_smoke.py" \
  "$MS_WHEEL" --offline --python "$MS_PYTHON" \
  --constraints "$MS_RELEASE/dependencies.txt" --extra embeddings
```

Use the same extra selection as checkpoint 2. This runner owns isolated uv tool,
Skill and Dataset locations; it checks resources, CLI/doctor, MCP discovery and
minimal dispatch, then removes its temporary installation. It does not prove all
business paths, model availability, actual project launch settings, or that an
existing Agent session has reloaded.

Add bounded installed-path checks for the changes being delivered. Existing
`tests/run_precheck_delivery_smoke.py`, `tests/run_geo_recovery_smoke.py`, and the
applicable evaluation session recipes cover different claims; inspect their inputs
and effect boundaries before selecting them. A video decoder change requires real
installed decoding; a Plan execution change requires its concurrency/recovery
checks. Unrelated Tool discovery cannot substitute for those checks. Broad model
or media reevaluation is necessary only when the changed behavior warrants it.

For installed-code tests, remove `PYTHONPATH`, avoid the checkout's `src` injection
(`pytest -o pythonpath=''` when applicable), and verify the imported package comes
from the isolated installation. Use synthetic or approved fixture inputs and keep
outputs outside fixtures. Provider calls, media egress, and model downloads retain
their own authorization boundaries.

Proceed only with an explicit result for required checks. A failed or unperformed
required check remains unfinished. If asked only to prepare or review the procedure,
stop before the actual switch; procedure readiness is not installation permission.

### 4. Switch the selected installation and project resources

Before changing actual targets, disclose the exact artifact, destinations,
dependency delta, configuration changes, and recovery conditions. Continue under
existing authorization when it covers those effects; ask only for missing choices
or authority. Retire affected old Host writers through their normal lifecycle
before replacement or migration; do not terminate an unrelated Agent session.

For the existing `uv tool` route, with `MS_WHEEL_SPEC` set to the exact wheel path
plus retained extras (for example `/absolute/release/package.whl[embeddings]`):

```bash
uv tool install --offline --force --no-python-downloads \
  --python "$MS_PYTHON" --constraints "$MS_RELEASE/dependencies.txt" \
  "$MS_WHEEL_SPEC"
```

Omit `--force` on first installation. Use an interpreter outside the tool
environment being replaced. Keep a released artifact at a stable retained path;
`dist` or a temporary filename is not an immutable release channel. Installing
extras alone does not enable capabilities or authorize model downloads.

Synchronize all four project Skills from the same verified release after checking
local customizations. Preserve the current management method:

- **Project managed by `npx skills`:** use the installed/cached verified manager
  version, the same project/agent target, and an explicit four-name allowlist.
  Run from the actual Honeycomb. Resolve `MS_SKILLS_VERSION` and
  `MS_SKILL_SOURCE` to that manager version and a retained verified release export;
  do not use `latest` as a reproducible version or quietly change the lock source.

  ```bash
  npx --offline "skills@$MS_SKILLS_VERSION" add "$MS_SKILL_SOURCE" \
    --skill mediasense mediasense-precheck mediasense-plan mediasense-apply \
    -a codex --full-depth -y
  npx --offline "skills@$MS_SKILLS_VERSION" ls --json
  ```

  Preserve unrelated lock entries. Verify each selected entry's source and
  manager-computed hash, plus every installed Skill file against the wheel.
  A local source must remain available for restoration; if the existing source is
  a changing checkout, freeze it for the operation or explicitly choose a retained
  source. Do not silently repoint the project lock or mutate it by hand.
- **Explicitly unmanaged directory:** use the selected executable's
  `mediasense skills install --target <absolute-skill-directory> --json` for a
  fresh install, or `mediasense skills upgrade --target <absolute-skill-directory>
  --json` for replacement. Install refuses conflicting content; upgrade replaces
  only the four packaged MediaSense directories as one recoverable set. These
  commands do not maintain an npx lock.

For a new Codex connection, minimally merge into the selected
`<honeycomb>/.codex/config.toml`:

```toml
[mcp_servers.mediasense]
command = "mediasense"
args = ["mcp"]
```

A valid existing command or credential-loading wrapper needs no replacement when
it resolves to the intended executable and environment. Preserve unrelated TOML
and MCP servers. Resolve conflicting/invalid configuration explicitly; do not
fall back to a user-level configuration file. Codex must trust the project to load
its project configuration. Other clients use their own local registration.

### 5. Verify the actual executable and loaded session

Resolve the actual executable again. Check its version, doctor output, dependency
versions, package files, and seven Tool contract IDs/digests against the selected
wheel and dependency plan. A shell success is not proof of the actual MCP launcher's
environment. Use the registered launcher for a bounded diagnostic Host check,
without displaying secrets or opening a live Dataset as a smoke test.

The existing `tests/run_global_cli_smoke.py --executable <absolute-executable>
--expected-version <selected-version>` checks the exact installed CLI and minimal
MCP dispatch on temporary inputs. It supplements the content and launcher checks;
it does not verify the project's current Agent session or each changed capability.

Disk updates do not reload an existing process or loaded Skill. Start a new Agent
session in the trusted operational Honeycomb when needed, and verify that it loads
the selected project Skills and the intended Host. Retain evidence that the Host
was launched from the verified executable after the switch; without a runtime
build ID, matching versions/digests alone cannot exclude an old process. Match the
Host's initialization version and Tool contract digests to the verified
installation. Discover exactly these seven MediaSense Tools (other servers may expose additional Tools):

- `mediasense.dataset.open`
- `mediasense.precheck.run`
- `mediasense.precheck.read`
- `mediasense.plan.work`
- `mediasense.geo.query`
- `mediasense.apply.run`
- `mediasense.apply.read`

If the client cannot expose part of this evidence, state that limit; do not infer
it from files. If a new Human-started session is still needed, report the machine
installation as verified and the session verification as pending. Business Run
resumption, network decisions, and Apply effects remain with their owning stage
and exact retained references; setup verification does not authorize them.

### 6. Record evidence and close at the verified scope

For repository-managed releases/upgrades, append a concise record to the existing
capability/installation ledger at
`docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md`.
Retain source commit/diff, wheel SHA-256, Python/extras/dependency delta, actual
installation and Skill targets, manager/lock identity, test results, session
verification, rollback limits, and any pending handoff. Reuse the current change
or evaluation session for detailed evidence; do not create another release registry.
Keep bulk outputs, wheels, raw logs, secrets, and media outside Git.

For an installed user's setup without a checkout, give the same scoped receipt in
the user's existing work record. Do not require creating a repository or evaluation
session just to install MediaSense. Never replace a historical failure or limited
acceptance with a broader success claim.

## Recovery and rollback

A failed checkpoint does not authorize continuing to the next effect. Inspect what
actually changed. Preserve working components and recover through their owning
installer or Skill manager; do not assume a nonzero command rolled back every
prior step. The CLI installer and project Skill manager do not form one atomic
transaction. Keep business use stopped until their contents agree, or restore the
previous verified set, including lock entries and configuration changes.

Rollback to the retained wheel is valid only if it supports the current Dataset
formats. Before any store migration, retire incompatible writers and retain a
consistent backup. If stores have advanced beyond the old release's support,
restore a valid pre-migration backup or keep a compatible executable. Never edit
version markers, transplant a single stage database, or erase Results merely to
make an older executable open them. Application version changes alone do not
invalidate all PreCheck work. Dataset deletion or resetting a business Run is a
separate decision.

## Maintaining the runbook

Update this source in the same change as any altered installation prerequisites,
packaging, manager behavior, client integration, or acceptance claim. Keep specific
release identities and observed machine state in the ledger, not in this reusable
procedure. Fix the invariant and its authoritative home; keep methods replaceable.

The packaged copy has no independent authoring authority. Refresh it from the
repository root and validate using the existing development environment:

```bash
cp readme/installation.md src/mediasense/_resources/skills/mediasense/references/installation.md
python -m pytest -q tests/test_honeycomb_integration.py tests/test_runtime_cli.py
```

The integration check compares the canonical file, packaged snapshot, and a
locally copied Skill byte for byte. The distribution runner also rejects a wheel
that differs from the selected source or runbook. Run its `--verify-only` check on
the built artifact before installation; the normal distribution check adds actual
isolated execution. Keep links inside the snapshot portable: same-document anchors
work offline, and repository-only references name their authoritative paths.
These checks enforce source/delivery consistency; the contributor still verifies
commands and evidence against real tool behavior when it changes.

## Prerequisites and optional capabilities

MediaSense requires Python 3.11 or newer. macOS is the first product-certified
platform. Linux can run the Python package, but removable-volume and Apply
filesystem behavior is not certified. Windows and `pipx` are not certified routes.
The CLI includes an on-demand stdio MCP Host, launched by the client and closed
with its connection. It is not a daemon. Codex is the first certified client;
other clients require their own integration acceptance.
`uv` and system tools are prepared through trusted channels; installation does not
bootstrap them.

ExifTool supplies complete metadata extraction; ffprobe (distributed with FFmpeg)
inspects video. Frame decoding uses the package's PyAV dependency and local FFmpeg
libraries. The `video_decoder` doctor check establishes dependency presence;
installed execution establishes that the decoder actually works. No decoder or
model is downloaded during a Run.

The `embeddings` extra installs local encoder dependencies in the same environment
as the MCP Host. New enabled profiles recommend DINOv3 ViT-B/16 at **384px**.
Existing explicit ChineseCLIP profiles keep their model selection. Prepare the
pinned local assets using the DINOv3 procedure below before enabling it. The `local-models` extra installs the fixed sensitivity dependencies below.
Its transitive NudeNet package contains a 320 weight, which is not the selected
640 model. Both selected assets must be prepared explicitly at local paths. Model configuration remains disabled by default. Extras,
weights, configuration, and actual execution each prove different prerequisites.
There is no automatic model download or remote fallback.

The optional checkout helper `scripts/install.sh` accepts `--offline`, `--force`,
`--embeddings`, and `--local-models`. It invokes `uv tool install` on the current
checkout and declared dependency ranges. It does not consume `uv.lock`, select an
exact release, preserve existing extras, or complete this runbook. Use it only when
that source/dependency behavior is intended; the verified release path above uses
an explicit wheel and constraints. It never configures Skills or an Agent client.

## Open a Dataset

No separate initialization step is required. Open a media source directly:

```bash
mediasense dataset open /Volumes/PhotoDisk/Photos
```

MediaSense searches in this order:

1. an explicitly supplied `--workspace`;
2. `<volume-root>/.mediasense/datasets/` when the source is on a non-system mounted volume;
3. `~/Library/Application Support/MediaSense/datasets/` on macOS.

For an isolated installation or test environment,
`MEDIASENSE_DATA_HOME=/some/path` overrides the machine-local application-data
base. It does not override an explicit per-Dataset `--workspace`.

If no matching Dataset exists, an eligible external source receives a portable
workspace on that volume. Otherwise MediaSense creates a local workspace and
reports why portable placement was unavailable. Existing corrupt, ambiguous, or
incompatible higher-priority state is an error; it is never hidden by silently
creating a lower-priority Dataset.

Every successful open reports the exact source, stable `dataset_ref`, workspace,
selection tier, loaded configuration files, and Provider credential, capability,
and data-handling facts. Dataset databases, derived Artifacts, Results, Plans,
Apply journals, and Receipts remain together in that workspace. Credentials,
Agent-client settings, and shared model downloads do not travel with the Dataset.
Neither a source path nor a Dataset workspace selects or implies a Honeycomb
directory.

Inspect an existing workspace without opening stage stores:

```bash
mediasense dataset inspect /path/to/dataset-workspace
```

Use an explicit location when necessary:

```bash
mediasense dataset open /Volumes/PhotoDisk/Photos \
  --workspace /Volumes/WorkspaceDisk/media-project
```

The workspace must not be inside the declared source root.

## Configuration

The configuration files are optional. The runtime configuration loader reads
values in this order, with later layers overriding earlier ones:

1. built-in defaults;
2. `~/Library/Application Support/MediaSense/config.toml`;
3. `<dataset-workspace>/config.toml`.

Provider keys override individually. A Dataset `[embedding]` table replaces the
user-level embedding table as a whole: supply a complete enabled profile or
`enabled = false`. Command options such as `--workspace` select operation inputs;
there is no generic CLI override for every configuration key. A Dataset
`[sensitivity]` table likewise replaces its entire user-level table.

Common configuration sections are shown below. The selected release's
`src/mediasense/runtime/config.py` defines its complete accepted key set;
capability-specific additions must be documented when their configuration is wired
into that release.

| Section | Keys | Default / interpretation |
| --- | --- | --- |
| `metadata` | `assumed_timezone`, `output_timezone` | Both default to Asia/Shanghai; distinguish offset-less camera time from output presentation. Dataset overrides explicitly supplied keys. |
| `providers` | `amap_api_key_env`, `google_maps_api_key_env` | Names of credential environment variables; defaults below |
| `sensitivity` | `enabled`, `models.freepik`, `models.nudenet640` | Disabled by default; independent fixed profiles and local paths, as below |
| `embedding` | `enabled`, `model_id`, `revision`, `dimensions`, `device`, `batch_size`, `image_size`, `model_path` | Absent/empty table disables embedding. `enabled=true` without a model selects the fixed DINOv3 384 Core ML profile below. Explicit ChineseCLIP profiles retain their pinned revision/dimensions, CPU and batch 4 defaults. |
| `geo_network` | `proxy_url`, `ca_bundle`, `google_timeout_seconds`, `amap_timeout_seconds`, `minimum_interval_seconds` | Optional network profile; see [Geo network configuration](#geo-network-configuration) |

### Freepik and NudeNet 640 local sensitivity

Only these selected recipes are released. Freepik requires Apple Silicon MPS,
FP32 without autocast, official Timm 448px preprocessing, batch 4 (tail batches
use their actual length). NudeNet 640 uses CPU FP32, batch 1 and the unmodified
NudeNet 3.4.2 native color, padding and class-agnostic NMS behavior. The adapter
creates an explicit CPU ORT session because the library constructor ignores its
providers argument. Both routes enforce two CPU intra-op threads and one inter-op
thread. No device, model, remote service or automatic download fallback exists.
The supported dependency stack uses Python 3.11–3.13; actual numerical validation
and platform evidence are recorded in the sensitivity change's acceptance report.

`local-models` pins Torch 2.7.0, Torchvision 0.22.0, Transformers 4.57.6, Timm
1.0.20, NumPy 2.2.6, Pillow 12.3.0, safetensors 0.8.0, huggingface-hub 0.36.2,
NudeNet 3.4.2, onnxruntime 1.22.1 and opencv-python-headless 4.11.0.86.
Retain compatible existing dependencies using the workflow constraints. This
stack matches the existing DINOv3 Torch/NumPy/Pillow pins; adding local-models
does not select or reconfigure embedding. Other platforms are not certified by
the macOS acceptance, and a package install alone does not establish MPS support.

Prepare retained copies of already verified assets outside source media,
Datasets, Downloads and evaluation code. Choose an absolute machine-local models
directory; copy exactly the following files and verify SHA-256 before enabling:

| Model / required file | Content SHA-256 |
| --- | --- |
| Freepik snapshot `config.json` | `39f53e86cc4868e0e11396b523c906f376621f54c1025ffc9ee2ee840542a41b` |
| Freepik snapshot `model.safetensors` | `024a9d4818fae2656403bf626c9f8c9e7789c2da274749fbebb1060d8fdaa7ab` |
| NudeNet `640m.onnx` | `04fe3d77980780c1f8297dc6d7f942fd5b3abe6942a188f742a85241e4f634eb` |

Freepik revision is `15b85477e4fd2000db76ae9aae0f89a72f95e2e3`.
The 640 asset was retained from SimonJoz/nudenet mirror revision
`2b20805bd4ab2a9edbbb99fa862f68411c00286a`; official bytes were not independently
obtained. Preserve this source limitation. Neither a filename nor the bundled
320 weight substitutes for the pinned content. Production imports no evaluation
scripts. Missing assets remain an unprepared prerequisite.

```toml
[sensitivity]
enabled = true
[sensitivity.models.freepik]
enabled = true
profile = "freepik-ordinal448-mps-fp32-v1"
model_path = "/absolute/local-models/freepik-snapshot"
device = "mps"
precision = "float32"
batch_size = 4
[sensitivity.models.nudenet640]
enabled = true
profile = "nudenet640-native-cpu-fp32-v1"
model_path = "/absolute/local-models/640m.onnx"
device = "cpu"
precision = "float32"
batch_size = 1
```

Only enabled and model_path are needed per selected model; the other values
resolve to the shown fixed recipe and conflicting values are rejected. Omitted
models are disabled. The total enabled flag defaults to false. The Dataset table
replaces the user table entirely. Unknown names/keys and invalid types fail new
execution explicitly. Old `device/nsfw_model_id/nsfw_revision` tables require
explicit migration; no automatic Falconsai/320 replacement or config rewrite.

Dataset Open reports the effective selection and config errors without importing
models. `doctor --json` reports each selected model's dependency/file prerequisites
and `execution=not_checked`; it performs no inference or download. A prepared
result still requires a bounded installed Run/Read check. Fresh work verifies
weights, runtime and actual device at loading. A missing prerequisite blocks with
`sensitivity_backend_unavailable`; restore the exact asset/backend and resume.
Resume retains the original selection and paths even after configuration edits.
Model/profile changes require a successor Run.

The admission estimate is 7 GiB for Freepik and 512 MiB for 640, each including
model residency and a batch; these are conservative estimates, not measured
peaks or additive whole-process use. The host-aware budget may grow to the
selected model demand while retaining 4 GiB of available-memory headroom,
and remains capped by any explicit budget. Other profiles retain the existing
4 GiB / half-available-memory default.
Insufficient capacity fails admission explicitly; it never shrinks the claim or
changes device. Models are released before their reservation ends. Cache-only
reuse needs neither that model memory reservation nor optional libraries/weights.

Execution facts have public read paths: `precheck.run` status with
`include=["diagnostics"]` reports the frozen resource budget and per-model summary;
`include=["local_execution"]` adds batches through the existing `page` selector.
`precheck.read` review with `include=["local_execution"]` reads the immutable
snapshot through `execution_page`. The two paged Run detail kinds are separate;
Read selects one of local_execution and execution_boundary per call. A shared
batch is counted once across its Work rows. Requested and actual inference input
counts, processing/load wall times and current versus reused scope stay distinct.
A null load time does not prove loading was separable from an adapter call.
Historical Results without that snapshot explicitly report not_recorded; Read
never joins mutable Work to manufacture missing execution history.

Unexpected library load exceptions surface as execution failures. Only positively
identified missing files/dependencies, forbidden fallback configuration or an
unavailable requested device/provider produce a recoverable backend prerequisite.

Each actual prepared high-resolution still or sampled video frame receives its
own Source Item Observation with exact input Evidence. Freepik retains all four
native probabilities and cumulative events; 640 retains every native instance,
including repeated labels and face/covered labels, in oriented input pixel xyxy.
No region is inferred from an absent property. A successful no-box detection is
available with an empty list. Model disagreement and failures remain attributed
evidence for Plan; no result authorizes remote processing.

Disabling a model excludes its cached outputs from **new** Results and records
not_checked. Existing Results and caches are retained; re-enabling can reuse them.
Reading retained V1 scores and thresholds (including 99/33) requires no model
packages or weights. Historical missing positions/instances/input bindings remain
unknown and sealed bytes never change.

PreCheck private format 19 and Run snapshot 9 additionally retain complete
ordinary Run preparation requirements and direct input bindings. Opening a
supported format-17/18 workspace adds the Run-owned immutable preparation table
and advances the store marker; no Work outputs, existing Run snapshots or Result
bytes are transformed. Large frozen inputs are stored separately from frequently
updated progress facts. Historical Results without recorded preparation report
it as missing, and cannot acquire guessed lineage. Older writers reject the new
version. Before an authorized daily upgrade, finish/cancel old active Runs
with the old build or verify that the new build can retain their exact recipe;
legacy sensitivity Runs cannot be converted into Freepik/640 while resuming.
Use a consistent pre-upgrade Dataset backup and retained wheel for rollback;
do not downgrade a version marker on state that has received new writes.

Ordinary and high-resolution stills remain prepared together for selected sources
even when models are disabled; valid preparation profiles reuse independently.

### DINOv3 384 local embedding

The recommended new profile is `timm/vit_base_patch16_dinov3.lvd1689m`, revision
`c6a5fb7d12bbd3cf3b0079253141c3332aaed7da`. This is the accepted timm release,
not a claim of numerical equivalence to the gated Meta checkpoint. The original
safetensors SHA-256 is `1f9ed8a2378d65e24bb710ba522ac9fa7be4e036d7aefb4384ce022833926332`.
The shipped `mediasense/_resources/dinov3-384.json` pins the exact compiled files,
preprocessing, feature semantics and runtime. Never substitute the 512px export.

| Platform | Released DINOv3 backend and support |
| --- | --- |
| Apple Silicon macOS 15+ | Core ML, fixed batch 1, `ComputeUnit.ALL`. Numerically validated on M5 Pro/macOS 26.4.1; other eligible hardware requires a local inference check. Actual CPU/GPU/ANE dispatch is unmeasured. |
| Intel macOS | Unavailable in this release. Core ML tools has Intel wheels, but the verified Torch 2.7/Torchvision 0.22 preprocessing stack has none. Torch 2.2.2 has Intel wheels and could support a separately validated CPU route; it is not an approved replacement. |
| Windows | Unavailable in this release. Torch 2.7/Torchvision 0.22 have Windows x64 wheels, making a future explicit CPU/CUDA adapter feasible; Core ML prediction has no Windows runtime. No Windows numerical or installed-path acceptance exists. |
| Linux | DINOv3 is not released on this platform; no automatic CPU fallback. |

The Apple Silicon extra pins Torch 2.7.0, Torchvision 0.22.0, Core ML tools 9.0,
NumPy 2.2.6 and Pillow 12.3.0. Use Python 3.11–3.13 for this dependency stack
(the actual validated interpreter is 3.13.5). Core-package Python support does
not establish optional backend support. `local-models` users also select
`embeddings` when they need DINOv3. For an upgrade, this changes Torch/NumPy if
necessary; retain other compatible dependencies using the workflow constraints.
Dependency changes can invalidate earlier vectors without changing the chosen
ChineseCLIP model. Do not rebuild existing Dataset results during installation.

Prepare an exact retained copy of the accepted `vision.mlmodelc` export. In this
repository its original source is the `model.snapshot_path` in
`eval/sessions/260911-0953-dinov3-resolution-384/config-384-coreml-batch1.json`.
Use the selected installed interpreter and the selected release's script:

```bash
MS_HOST_PYTHON=/absolute/path/to/installed/mediasense/environment/bin/python
"$MS_HOST_PYTHON" "$MS_RELEASE/source/scripts/prepare_dinov3.py" \
  --source /absolute/path/to/verified-384-export
```

The script checks every compiled file against the packaged recipe, copies only
those files atomically, and verifies the destination. An existing correct copy is
reused; conflicting content is refused. The default destination is
`~/Library/Caches/MediaSense/models/dinov3-vitb16-384-c6a5fb7d12bbd3cf3b0079253141c3332aaed7da`.
`--destination` can select another absolute machine-local directory. No model is
bundled into the wheel. This command does not download weights, convert a graph,
change configuration, or touch Dataset state.

If the accepted export is missing, preparation remains incomplete. The retained
source checkpoint and conversion/numerical recipe are documented in the 384 eval
report and `eval/sessions/260910-2212-dinov3-vitb16-512/convert_coreml.py` (which
reads 384 from its input config). Rebuilding needs that fixed checkpoint, timm
1.0.20 and the reviewed mixed graph recipe, followed by numerical acceptance and
compiled-file identity review; do not silently regenerate a different export or
change checksum expectations to accept it. Downloading approved fixed public
weights is an installation action with explicit authorization, never a Run action.

New explicit configuration can be as small as:

```toml
[embedding]
enabled = true
```

It resolves to the following full supported recipe (the machine-local path may
be overridden; all other listed values are fixed for this release):

```toml
[embedding]
enabled = true
model_id = "timm/vit_base_patch16_dinov3.lvd1689m"
revision = "c6a5fb7d12bbd3cf3b0079253141c3332aaed7da"
dimensions = 768
image_size = 384
device = "coreml"
batch_size = 1
# model_path = "/absolute/path/to/prepared-384-export"
```

The input is Pillow RGB without an additional EXIF transpose, uint8 bilinear
antialiased square resize to 384, then FP32 rescaling and ImageNet normalization;
no crop. Output is final-LayerNorm CLS (768 dimensions), with producer L2 and
float32-le storage. The graph uses FP16 convolution/MLP and FP32 attention,
normalization, residuals, RoPE and I/O. CPU preprocessing uses two intra-op and one
inter-op thread. These choices, model/compiled checksums, adapter recipe revision,
library versions and OS/backend identity enter the encoder cache identity;
input artifact dependencies and normalization enter existing Work identity.
Changing the model or recipe creates distinct vectors; valid upstream preparation
can be reused. Copying identical weights to another path does not invalidate them.

`mediasense doctor --json` reports configured/disabled separately from DINOv3
prerequisites (`prepared` or `unavailable`), and always `execution=not_checked`.
It verifies versions, platform and local checksums without inference or network.
Run loads the graph before admitting embeddings. Missing/unusable prerequisites
produce `embedding_backend_unavailable`; prepare the same recipe and resume.
A changed encoder identity requires restoring it or starting a successor Run.
Unexpected prediction errors surface as execution failures, never remote fallback.
A prepared doctor result must be followed by a bounded installed Run/Read check.

Grouping continues to use the existing temporal/spatial scales and representative
selection (top half, exact limit 256, comparison budget 65,536). The accepted 384
results at scales 0.311/0.85 had 156/99 groups; model quality acceptance alone does
not decide production granularity. Installation records the selected granularity
and its Human decision in the existing migration ledger.

### Existing ChineseCLIP configuration

An explicit ChineseCLIP model remains ChineseCLIP, including old complete tables
that omitted `enabled`. Dataset tables still replace the entire user-level table.
No installer rewrites user/Dataset model configuration or sealed Results. To adopt
DINOv3 for one existing Dataset, explicitly replace its profile and start a new
Run when wanted; leave existing Results intact. An empty new table does not enable
embedding. Legacy pinned local ChineseCLIP configuration remains:


```toml
[providers]
amap_api_key_env = "AMAP_API_KEY"
google_maps_api_key_env = "GOOGLE_MAPS_API_KEY"

[embedding]
enabled = true
model_id = "OFA-Sys/chinese-clip-vit-huge-patch14"
revision = "503e16b560aff94c1922f13a86a7693d36957a4f"
dimensions = 1024
device = "cpu"
batch_size = 4
```

Configuration names environment variables that contain credentials; credentials
themselves must not be written to a Dataset workspace. Credential presence is a
capability fact, not authorization. PreCheck keeps zero external effects until a
Human authorizes the exact frozen Provider request batch and disclosed policy.
Diagnostics report credential and capability status plus Provider data handling;
an unknown policy is reported as `unknown`, never as `none`.
`MEDIASENSE_CONFIG_HOME` may select another machine-local configuration base.

Other setup has distinct owners: `MEDIASENSE_DATA_HOME` selects the default
Dataset storage base; the Agent client's MCP registration selects its executable
and inherited environment; ExifTool, FFmpeg, Python extras and local model weights
are installation prerequisites. They are not additional `config.toml` keys.
Scope decisions, external-effect authorization and Plan preferences belong to
their Dataset/Run/Plan operations rather than persistent provider configuration.

Internal producer parameters and evaluation settings are not automatically user
configuration. Dataset Open reports the effective supported configuration;
`doctor` checks installation facts. Use the exact release's configuration and
installed execution evidence to distinguish a supported setting, an unavailable
prerequisite, and a capability that is not yet connected to the Host.

### Manufacturer knowledge

For reading, adding or revising rules, start with the adjacent runbook at
`mediasense/_resources/manufacturers/README.md` in builds that ship it
(`src/mediasense/_resources/manufacturers/README.md` in a checkout). It explains
`when`, `apply`, `basis`, evidence, verification and withdrawal. That file is the
single authoring source for the maintenance guide; the file contract owns semantics.

In builds containing manufacturer knowledge, the package supplies a YAML baseline
under `mediasense/_resources/manufacturers/`. Put personal `.yaml` or `.yml` files
in `manufacturers/` beside the user `config.toml`. On macOS this is normally
`~/Library/Application Support/MediaSense/manufacturers/`; the existing
`MEDIASENSE_CONFIG_HOME` also selects this root. Dataset workspaces do not add a
second knowledge authoring directory.

Each file has `schema_version: 1` and a `rules` list. Each rule has a stable `id`
and explicit `operation: add / replace / disable`. A replacement supplies a whole
rule; a disable supplies its reason. Copy one reviewed rule when customizing,
rather than a full baseline that would hide later improvements. Conditions,
effects, sources and limitations follow the shipped
`_resources/contracts/manufacturer-knowledge.schema.json`; the human-readable
authority and examples are `docs/spec/contract/manufacturer-knowledge/` in the
selected source. Invalid YAML, duplicate IDs, unknown fields and invalid patterns
are explicit configuration errors.

Standard GPS and source-dimension mappings use `tag_pairs` in `apply.fields`;
each coordinate or dimension pair comes from the same file. Dimension rules read
the source media only. Custom `integer` fields preserve exact integer values.

The existing TOML separates camera-time assumptions from presentation:

```toml
[metadata]
assumed_timezone = "Asia/Shanghai"
output_timezone = "Asia/Shanghai"
```

Both default to Asia/Shanghai; Dataset configuration overrides explicitly supplied
keys. `mediasense doctor --json` and Dataset Open report metadata settings,
knowledge identity, source files, replacements (including the overridden bundled
source), and disabled rules, with `execution: not_checked`.
A new Run rereads current files and stores its full snapshot in the existing
PreCheck store. Resume retains that snapshot; edits affect successor Runs, not
sealed Results. Read delivers the actual rule/source evidence with the resulting
attributes. Configuration alone does not prove a rule has processed media.

If current manufacturer YAML is invalid, Dataset Open reports its error without
claiming an active knowledge snapshot. Existing Results and Runs with a frozen
snapshot remain accessible after a Host restart. New work still fails validation;
fix the file before starting another Run. `doctor` continues to report the error.

### Geo network configuration

The Geo contract at `docs/spec/contract/geo-query/` defines target-region
routing, finite execution, cumulative accounting and explicit recovery. Bundled
Natural Earth 5.1.1 geometry is used offline; a 500 m boundary/coast guard reports
uncertainty instead of guessing. It does not certify real geographic accuracy.
Mainland routes use AMap and overseas routes use Google. A missing suitable
provider or uncertain route is reported before new effects; a provider outage
preserves completed components and blocks until its condition is addressed.

The Host accepts an optional `geo_network` table in the existing user
or Dataset configuration, for example:

```toml
[geo_network]
# Set a proxy only after the user has selected and authorized this receiver.
# proxy_url = "http://127.0.0.1:7890"
google_timeout_seconds = 3
amap_timeout_seconds = 15
minimum_interval_seconds = 0.3
# ca_bundle = "/absolute/path/to/approved-ca.pem"
```

Without an explicit proxy, the actual Host's environment/system HTTP(S) proxies
apply; `ALL_PROXY` supplies missing HTTP/HTTPS entries. Only HTTP/HTTPS proxy
protocols are supported. `NO_PROXY` / `no_proxy` remain effective. An explicit
`ca_bundle` takes precedence over `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, and
`CURL_CA_BUNDLE`; otherwise system CA validation remains enabled. Unsupported
proxy protocols or invalid CA configuration fail explicitly. No model download,
map reachability probe, or automatic proxy setup is performed.

Configuration reports show sanitized proxy receivers, CA source, and an effective
profile identity, with reachability `not_checked`. Parent shell variables are not
proof of the MCP child's environment: explicitly pass required proxy/CA variables
through the existing launcher, or configure the existing MediaSense config file.
After file configuration changes, a paused/blocked Run reloads its Geo network
settings on resume and requires matching confirmation before new effects. Changed
process environment requires a newly launched Host. Do not terminate an active
Agent merely to claim the disk update is already loaded.


## Uninstall and cleanup

For an installation managed by uv:

```bash
uv tool uninstall mediasense
```

Uninstalling the executable leaves Dataset workspaces, configuration, credentials,
project Skills/locks, and model downloads intact. Remove selected project entries
through their existing manager only when requested. Inspect retained state before
any separate cleanup; uninstalling is not authorization to delete media or Results.
