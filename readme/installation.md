# Installation and first use

MediaSense 0.7 is a pre-release local product for Python 3.11 or newer. macOS is
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
for the current checkout and does not bootstrap `uv`, system packages, optional
models, Agent Skills, user-level configuration, or project-level configuration.
Use `--offline` to prohibit dependency downloads or `--force` to explicitly
replace an existing MediaSense tool environment.

For a built release artifact, install the exact wheel instead:

```bash
uv tool install ./dist/mediasense-0.7.0-py3-none-any.whl
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
selection tier, loaded configuration files, and offline policy. Dataset databases,
derived Artifacts, Results, Plans, Apply journals, and Receipts remain together in
that workspace. Credentials, Agent-client settings, and shared model downloads do
not travel with the Dataset. Neither a source path nor a Dataset workspace selects
or implies a Honeycomb directory.

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

The initial configuration files are optional. MediaSense reads values in this
order, with later layers overriding earlier ones:

1. built-in defaults;
2. `~/Library/Application Support/MediaSense/config.toml`;
3. `<dataset-workspace>/config.toml`;
4. explicit command options.

Supported initial keys are:

```toml
[runtime]
offline = true

[providers]
amap_api_key_env = "AMAP_API_KEY"
google_maps_api_key_env = "GOOGLE_MAPS_API_KEY"
```

The default is offline. Configuration names environment variables that contain
credentials; credentials themselves must not be written to a Dataset workspace.
Every diagnostic reports only `configured` or `not_configured`.
`MEDIASENSE_CONFIG_HOME` may select another machine-local configuration base.

## Upgrade and rollback

Before upgrading, keep the portable Dataset workspace with the media and back it
up like other valuable project state. Upgrade the installed tool through the same
trusted channel used to install it. MediaSense checks manifest and component-store
versions before ordinary use and refuses newer or unsupported state without
rewriting it.

MediaSense `0.7.0` replaces the public PreCheck Read `inspect` and `traverse`
operations with `review`, `expand`, and `resolve`, without a compatibility
layer. Replace an older tool environment with the exact trusted current `0.7.x`
artifact; do not keep both under the same `mediasense` command or infer
compatibility from seven-Tool discovery alone:

```bash
uv tool install --force ./dist/mediasense-0.7.0-py3-none-any.whl
```

Application versions follow SemVer during `0.y.z`: minor releases may contain
documented breaking CLI, Host, manifest, or store changes; patch releases are
compatible fixes. A changed application version alone never invalidates all
PreCheck work.

The supported `0.7.x` combination is:

| Surface | Supported value |
| --- | --- |
| Application | `0.7.x` |
| Dataset manifest | `1` |
| PreCheck store | `17` |
| Plan store | `2` |
| Geo journal | `1` |
| Apply store | `2` |
| Packaged Skills | From the same MediaSense release |

PreCheck store 16 has no supported migration to 17. Preserve an existing
`0.3.x` Dataset workspace for rollback and create a distinct workspace for
`0.7.x`; do not copy only its PreCheck database or edit its version marker.

After replacing the CLI, upgrade the four release-matched Skills in each
explicit Honeycomb:

```bash
mediasense skills upgrade --target <absolute-honeycomb>/.agents/skills
```

This operation changes only the four MediaSense Skill directories, preserves
unrelated Skills, and rolls back its own replacements if the set cannot be
completed. Start a new Agent session afterwards so it loads the `0.7.x` Skills
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
