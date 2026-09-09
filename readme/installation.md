# Installation and first use

MediaSense 0.8 is a pre-release local product for Python 3.11 or newer. macOS is
the first product-certified platform. Linux can run the Python package, but its
removable-volume and Apply filesystem behavior is not yet certified. Windows is
not currently supported.

## Install

For Agent-guided first use, first install the `mediasense` product entry Skill
through the Agent client's standard local-Skill mechanism into the Honeycomb you
selected. For Codex, that location is `<honeycomb>/.agents/skills/`. The loaded
entry Skill can then inspect the machine and explain the exact CLI install,
complete release-matched Skill installation, and project MCP configuration before
requesting permission to change them. A Skill cannot load itself, so this initial
entry-Skill acquisition is the one prerequisite outside the MediaSense workflow.

The MediaSense source checkout is not an implicit installation target. Skill
files stored under `src/mediasense/_resources/skills/` are packaged release
assets; install them only into the explicitly selected operational Honeycomb.

To install the CLI directly, use a trusted checkout or release artifact. This is
a machine-level executable installation, independent of any Honeycomb and any
Dataset workspace.

From a trusted MediaSense checkout, install the package and its locked Python
dependencies with:

```bash
./scripts/install.sh
```

The script is intentionally small and reviewable. It invokes `uv tool install`
for the current checkout and does not bootstrap `uv`, system packages, model
downloads, Agent Skills, user-level configuration, or project-level configuration.
Use `--offline` to prohibit dependency downloads or `--force` to explicitly
replace an existing MediaSense tool environment.

For local visual embeddings, use `./scripts/install.sh --embeddings` (add `--force`
when replacing an existing installation). This installs the encoder dependencies
into the same environment as the MCP Host, not into a separate shell environment.
It does not download model weights. Provision a trusted pinned ChineseCLIP model
locally, then use the `[embedding]` table documented under [Configuration](#configuration).

The model is an adapter choice, not the compression contract. Use a revision that
is fully present in the local model cache and dimensions appropriate to that
model. `mps` and `cuda` require a usable corresponding device. The CPU default
avoids silently assuming an accelerator; measure its local cost before adopting
a large model for routine use. Set `[embedding] enabled = false` to disable it.
Absent configuration remains disabled and is reported as such. Dataset Open
reports the effective configuration; model loading is local-only and Run status
reports unavailable prerequisites. Restore the same encoder to resume a Run;
changing its model, library version or device requires a new Run. Sealed Result
context distinguishes actual execution, reuse, failure and comparison limits.

For local sensitivity evidence, use `./scripts/install.sh --local-models`, or
install the wheel with its `[local-models]` extra. It includes NudeNet 3.4.2's
packaged local weights and both detector dependencies. The pinned NSFW model and
processor must already exist in the local Hugging Face cache. `mediasense doctor
--json` checks the bundled NudeNet weights and reports the user configuration;
actual backend execution is checked by Run. There is no automatic model download
or remote fallback. Sensitivity defaults to disabled, including when an empty
`[sensitivity]` table is present.

For a built release artifact, install the exact wheel instead:

```bash
uv tool install ./dist/mediasense-0.8.0-py3-none-any.whl
```

`uv` may download declared Python dependencies. MediaSense does not install
ExifTool, FFmpeg, local models, or other system software automatically.
`pipx` is not part of the initial certified installation path; compatibility may
be added after an isolated `pipx` acceptance run rather than inferred from similar
packaging behavior.

Verify the installed executable:

```bash
mediasense --version
mediasense doctor
```

`doctor` distinguishes required failures from optional capabilities. ExifTool is
needed for complete metadata extraction. FFmpeg and ffprobe are needed for video
inspection and frame extraction. Their absence does not make installation itself
invalid.

Installing a CLI in `PATH` does not make MediaSense available to every Agent. A
specific Honeycomb must separately contain its local Skills and MCP registration;
see [Agent integration](agent-integration.md).

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

The complete currently supported TOML key set is:

| Section | Keys | Default / interpretation |
| --- | --- | --- |
| `providers` | `amap_api_key_env`, `google_maps_api_key_env` | Names of credential environment variables; defaults below |
| `sensitivity` | `enabled`, `device`, `nsfw_model_id`, `nsfw_revision` | Disabled unless `enabled=true`; enabled profiles require a 40-character immutable revision; defaults: CPU and Falconsai/nsfw_image_detection |
| `embedding` | `enabled`, `model_id`, `revision`, `dimensions`, `device`, `batch_size` | Absent table disables embedding. Enabled profiles require model ID, pinned revision and dimensions; device defaults to `cpu`, batch size to `4` |

Example with both sensitivity detectors explicitly enabled, using an existing
local NSFW revision (replace the placeholder with its exact 40-character commit):

```toml
[sensitivity]
enabled = true
device = "cpu"
nsfw_model_id = "Falconsai/nsfw_image_detection"
nsfw_revision = "<local-40-character-commit>"
```

Each selected high-resolution still and sampled video frame receives a separate
outcome from each detector. NudeNet currently uses CPU or a locally available
CUDA ONNX provider; an unsupported device (including MPS for NudeNet) is reported
as backend-unavailable. The NSFW adapter supports the configured local PyTorch
device. Scores and effective thresholds remain evidence; they do not authorize
remote processing. Run records backend-unavailable as blocked and can resume
when the pinned local prerequisites become available. Changing an already
observed model, profile or backend identity requires a new Run.

Ordinary and high-resolution stills are prepared together for selected sources
even when both model capabilities are off; valid profiles reuse independently.

Example with local embedding explicitly enabled:

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

Internal producer parameters are not all exposed as user configuration. In
particular, the installed Host still uses the internal metadata timezone default
(`Asia/Shanghai`), and the sensitivity adapter has no Host configuration/wiring.
Do not treat these as options a user forgot to configure. Dataset Open reports
the effective supported TOML configuration; `doctor` checks installation facts,
but neither currently provides a complete inventory of every internal capability
and its missing product integration.

## Upgrade and rollback

Before upgrading, keep the portable Dataset workspace with the media and back it
up like other valuable project state. Upgrade the installed tool through the same
trusted channel used to install it. MediaSense checks manifest and component-store
versions before ordinary use and refuses newer or unsupported state without
rewriting it.

MediaSense `0.8.0` replaces nested PreCheck requests with flat `action` and
`dataset_ref` inputs and updates the corresponding response contracts. The
run/read Tools still expose nine actions; the former `request` wrapper and
`operation` alias are unsupported. Replace an older tool environment with the
exact trusted current `0.8.x` artifact and update its Skills; matching Tool names
alone do not establish compatibility:

```bash
uv tool install --force ./dist/mediasense-0.8.0-py3-none-any.whl
```

Application versions follow SemVer during `0.y.z`: minor releases may contain
documented breaking CLI, Host, manifest, or store changes; patch releases are
compatible fixes. A changed application version alone never invalidates all
PreCheck work.

The supported `0.8.x` combination is:

| Surface | Supported value |
| --- | --- |
| Application | `0.8.x` |
| Dataset manifest | `3` |
| PreCheck store | `17` |
| Plan store | `3` |
| Geo journal | `1` |
| Apply store | `2` |
| Packaged Skills | From the same MediaSense release |

Older manifest/store formats without a supported migration are refused; do not
edit their version markers or copy only a PreCheck database into a new workspace.
An application upgrade does not automatically discard retained data. For a fresh
start, explicitly remove the selected Dataset workspace from discovery only after
deciding that its Results and recovery history are no longer needed. Preserve
source media and unrelated Dataset workspaces.

After replacing the CLI, upgrade the four release-matched Skills in each
explicit Honeycomb:

```bash
mediasense skills upgrade --target <absolute-honeycomb>/.agents/skills
```

This operation changes only the four MediaSense Skill directories, preserves
unrelated Skills, and rolls back its own replacements if the set cannot be
completed. Start a new Agent session afterwards so it loads the `0.8.x` Skills
and MCP Host.

Public Tool contracts are identified by their stable contract ID and exact schema
digest. Inspect the installed set with `mediasense tools list --json`.

Rollback is safe only while the older executable supports the current Dataset
formats. If it does not, it refuses writes and the user must restore a pre-migration
backup or reinstall a compatible version.

## Uninstall and cleanup

Remove the executable with:

```bash
uv tool uninstall mediasense
```

Uninstalling does not delete Dataset workspaces, configuration, credentials, or
model downloads. Inspect and remove those locations separately only after deciding
their retained Results and recovery history are no longer needed.
