---
id: "synthesis"
title: "MediaSense Fast Test Contract Synthesis"
type: delegation
status: active
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-2334-mediasense-test-contract"
depends-on:
  - "01-result-checker-sdk"
superseded-by: ""
---

# MediaSense Fast Test Contract Synthesis

## Closing judgment

The requester's intended direction is sound, with two important corrections
from current evidence:

1. Checker SDK's 400-line rule is not a preference. It is a machine-enforced
   hard limit for ordinary hand-written Python under the main package, with
   narrow, auditable exceptions for faithful upstream sources, registered pure
   declarative catalogs, and one frozen legacy root. It does not apply to tests.
2. Checker SDK has no written "well below 10 seconds" contract. Its six-worker
   default suite is currently about 8.6--8.8 seconds warm on this machine but
   took 16.08 seconds on the first measured run. It demonstrates a useful fast
   feedback design, not a durable cold-start guarantee.

MediaSense should adopt the principles, not copy the current mechanics. In
particular, it should establish one canonical `make test` developer gate, keep
external-fixture and scale work explicit, define a measured timing SLO, and
introduce a source-size ratchet for the existing oversized codebase. It should
not claim a sub-ten-second gate until its own selected suite passes reliably
within that budget.

## Identity and delegation finding

- MediaSense is already registered as active virtual Team `team:mediasense`,
  short name `MediaSense`, with workspace
  `/Users/chengyanru/repos/personal/mediasense` and `direct-write` results.
- Checker SDK is registered as active virtual Team `team:checker-sdk`, short
  name `chk.SDK`, with workspace
  `/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker`
  and `direct-write` results.
- Request 01 therefore had a valid autonomous local-workspace route. Its raw
  return is preserved unchanged in [01-result-checker-sdk](01-result-checker-sdk.md).

## What Checker SDK actually does

`make test` expands to:

```text
uv run --with pytest --with pytest-xdist python -m pytest -q -n 6 --dist loadfile
```

Pytest itself excludes `packaging` and `tokenizer_resource` markers. Other
responsibilities remain separate: `make check` covers checker-authoring
validation, while packaging, strict upstream parity, real local CSV regression,
and benchmarks have explicit commands. Ruff, formatting, type checking, and
coverage are not part of Checker SDK's `make test`.

The returned five-run measurement selected 2,186 of 2,216 items and reported
2,170 passed plus 16 skipped each time. Wall times were 16.08, 8.75, 8.75,
8.64, and 8.80 seconds. A serial comparison was about 28.79 seconds. MediaSense
independently reran the warm command: 2,170 passed, 16 skipped in pytest's
7.68 seconds; process wall time was 8.46 seconds. The Checker SDK worktree was
clean afterward.

The speed comes from a real boundary: small synthetic/redacted fixtures,
external and packaging work kept outside the default suite, almost no real
sleeps, and six-way file-level parallelism. It is not achieved by making all
checks implicit in one command. The 16 skips are also visible evidence that the
default green suite is not strict upstream-oracle parity.

## MediaSense current baseline

The current working-tree snapshot has materially different economics:

- `pyproject.toml` already makes `local_fixture` and `scale` opt-in, but there is
  no repository `Makefile` or single documented developer gate.
- One default pytest run reported 626 passed, 16 deselected, and one failure in
  134.21 seconds. The failed runtime-versioning test passed alone in 0.25 seconds
  and its four-test module passed in 0.32 seconds. This is an unresolved
  order/environment/flakiness signal, not a diagnosed cause.
- Ruff lint passed in about 0.14 seconds. Ruff format check currently fails with
  34 files that would be reformatted, so format cannot honestly be advertised
  as a passing gate without a separately reviewed cleanup.
- Of 83 tracked Python files under `src/`, 32 exceed 400 physical lines; the
  largest is `src/mediasense/apply/preparation.py` at 2,490 lines. Across tracked
  Python/Shell files under `src/`, `tests/`, and `scripts/`, 54 exceed 400.

These measurements were taken against the user's existing dirty worktree and
must be treated as a current development snapshot, not a clean-release
benchmark. No pre-existing modification was changed or normalized.

## Candidate contract for a later change

The next design/implementation slice should evaluate this contract rather than
blindly copy Checker SDK:

- `make test` is the canonical, offline, deterministic local gate. It includes
  Ruff lint plus the smallest pytest selection that still covers public
  behavior, schemas, state/failure semantics, and safe bounded integration.
- `make test-local-fixture` and `make test-scale` remain explicit opt-in layers.
  A packaging or installed-artifact target should be added only when a real
  release responsibility needs it.
- Keep marker selection authoritative in `pyproject.toml`; the Makefile should
  invoke it rather than duplicate the expression.
- Measure serial and 2/4/6-worker variants before choosing xdist. Checker SDK's
  `-n 6 --dist loadfile` is evidence, not a portable default; MediaSense's large
  test modules may create poor load balance or expose shared-state races.
- Define the initial speed SLO as five consecutive warm runs with median at or
  below 10 seconds, while recording warm max and one ordinary first-run value.
  Prefer a trend/ratchet check to a brittle cross-machine wall-clock test. Treat
  five seconds as an aspiration only after measurement supports it.
- Do not reach the budget by silently hiding required regression coverage.
  Slow tests move only when their responsibility is genuinely scale, external,
  packaging, or otherwise outside the default developer loop.
- Target ordinary hand-written `src/mediasense/**/*.py` at 400 physical lines,
  but begin with a baseline ratchet: no new oversized files and no growth of
  registered existing oversized files. Remove entries only through real
  responsibility-based decomposition. Allow only machine-verifiable generated
  or faithful-source exceptions; ordinary adapters, orchestrators, state
  machines, safety code, and evidence formatting remain governed.
- Keep test-file maintainability a separate review concern rather than falsely
  claiming Checker SDK's production-source limit already covers tests.
- Before declaring the new gate complete, resolve the current full-suite
  failure, establish a clean-tree timing baseline, inspect slowest tests, and
  verify any selected parallel mode for isolation and deterministic results.

This sequence follows confidence-per-second rather than speed alone: first make
the default scope explicit and trustworthy, then reduce its critical path,
while preserving slower evidence in named gates.

## Verification and acceptance

MediaSense independently checked the cited Checker SDK Makefile, pytest marker
configuration, AGENTS source-size rule, and executable line-limit test. It also
reran one warm `make test` successfully and confirmed no Checker SDK worktree
change. The raw result is accepted as sufficient for this research purpose.

The package closes only the requested investigation. No MediaSense Makefile,
test marker, dependency, formatting change, source split, or timing gate was
implemented. Those require a separate authorized design/implementation step
against a stable baseline.
