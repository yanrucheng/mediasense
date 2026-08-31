# Migration comparison

The comparison boundary is product installation, Dataset-local derived state, and
runtime invocation. AI Album remains historical evidence, not a dependency or a
target contract.

| Capability | AI Album evidence | MediaSense outcome | Classification | Remaining evidence |
| --- | --- | --- | --- | --- |
| Runnable installation | Docker image plus bind mounts, environment file, and repository-oriented invocation | One Python wheel and `mediasense` executable, with an explicit reviewable installer and no required container | `intentionally_changed` | Published-channel installation is not exercised because publication is not authorized |
| Dataset-adjacent derived state | `.similarity_cache/<input-name>/` under the input parent made caches travel with a mounted parent directory | `<volume-root>/.mediasense/datasets/<identity>/` keeps all Dataset-owned stores and artifacts together without writing inside the media root | `preserved` capability, `intentionally_changed` mechanism | Physical removable-volume and cross-machine certification beyond the simulated mount-path test |
| Cross-machine reuse identity | Primarily path/hash-derived cache addressing; no durable source-attachment or remount decision record | Stable Dataset manifest plus macOS volume UUID/root identity where available; mismatch blocks or requires audited rebind | `intentionally_changed` | Non-Darwin stable volume identity and broader filesystem matrix |
| Long-work continuation | Cache hits could avoid some recomputation but no durable product Run lifecycle established completion | Existing durable PreCheck Run, Work, Result, and dependency-specific reuse are preserved behind installed composition | `intentionally_changed` | Long-duration removable-drive interruption soak |
| Configuration and credentials | User configuration under `~/.config/ai-album`, credentials supplied through environment files | Machine and Dataset configuration have explicit precedence; credentials remain environment references and are redacted | `preserved` intent, `intentionally_changed` boundary | Future credential-provider integration if required |
| Agent Tool discovery | No MCP Tool Host or shared public Tool contracts | Standard stdio MCP discovery exposes Dataset open plus six accepted Tools; client registration remains client-owned | `not_comparable` | Codex is the first certified client; other MCP clients remain protocol-compatible only |
| Version and migration safety | Application version existed, but no integrated Tool/store compatibility or release system | Single package version, contract digests, Dataset/store versions, fail-closed compatibility, release notes, and rollback guidance | `not_comparable` | First real upgrade migration will require its own fixture and rollback proof |

The changed directory layout is not a regression: it retains the portability that
made AI Album's cache useful while replacing path-only association and destructive
cache repair with explicit Dataset identity, source verification, store versions,
and recoverable diagnostics.
