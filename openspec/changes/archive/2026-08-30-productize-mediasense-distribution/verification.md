# Verification

Verified on 2026-08-31 in the shared macOS worktree without resetting,
committing, publishing, invoking a live provider, or mutating real media.

## Product evidence

- `uv build --out-dir /private/tmp/mediasense-release-final-6xyCpH` built both
  `mediasense-0.2.0.tar.gz` and
  `mediasense-0.2.0-py3-none-any.whl` successfully.
- `uv run --python 3.11 python tests/run_distribution_smoke.py --offline
  /private/tmp/mediasense-release-final-6xyCpH/mediasense-0.2.0-py3-none-any.whl`
  completed with `distribution smoke: ok` after the Python 3.11 dependency cache
  had been populated by one explicit online installation.
- The smoke run inspected wheel metadata and entry points, installed into fresh
  temporary Tool/data/config roots, ran version and doctor, listed seven Tools,
  opened the same synthetic Dataset twice, installed all three Skills, completed
  a real MCP subprocess initialize and `tools/list`, called
  `mediasense.precheck.run` status without media effects, uninstalled the
  executable, and retained Dataset state.
- The reviewable installer completed once with `--offline`; a second invocation
  reported the existing identical installation and exited successfully.

## Regression and quality evidence

- `uv run --python 3.11 pytest -q`: 518 passed, 12 explicitly excluded by the
  repository's `local_fixture` and `scale` default markers.
- `uv run ruff check .`: passed.
- `openspec validate --all --strict --no-interactive`: 12 passed, 0 failed.
- Documentation validation inspected 63 Markdown files: zero missing required
  frontmatter fields, folder indexes, index entries, or local link targets.
- All three packaged Skills passed the Skill validator.
- `uv lock --check`, `bash -n scripts/install.sh`, and `git diff --check`: passed.

## Acceptance limits

- The external-volume precedence and changed-mount-path behavior are covered with
  isolated filesystem tests, and Darwin volume-UUID parsing is covered with a
  deterministic adapter test. No physical removable-volume or second-machine run
  was performed, so wider filesystem portability remains uncertified.
- No local model suite, live map provider, paid API, Hong Kong fresh replay, real
  media move, release publication, or package registry installation was run.
- Codex is the first documented complete Agent integration. The Host follows stdio
  MCP, but Claude, VS Code, Cursor, and other client-specific workflows remain
  protocol-compatible rather than product-certified.
- The repository contained concurrent uncommitted stage and contract work before
  this change. It was preserved; verification covers the combined working tree.
