---
title: "PreCheck corrections after the HK trajectory audit"
service_version: "MediaSense 0.8.0 working tree"
date: 2026-09-08
environment: "local macOS; isolated MCP subprocess; CPU"
model_id: "OFA-Sys/chinese-clip-vit-huge-patch14@503e16b560aff94c1922f13a86a7693d36957a4f"
dataset_version: "ai-album-hk-representative-v1 manifest media"
purpose: "Verify temporal interpretation, local visual execution, reuse, and input isolation"
baseline_ref: "eval-260908-1148-hk-trajectory-audit"
---

Source: `/Users/chengyanru/Downloads/ai-album-hk-representative-v1`.
API endpoint: local `python -m mediasense mcp` over stdio. No remote authorization,
Plan judging, or Apply execution. Recipe:

```bash
.venv/bin/python eval/sessions/260908-1329-precheck-corrections/run.py --fixture /Users/chengyanru/Downloads/ai-album-hk-representative-v1 --output /tmp/mediasense-controlled-corrections
# Add --full for all 2,134 hash-bound manifest media. Use a new output path.
```

Raw logs, prepared media, operator mapping and databases are local-only under the
chosen output. The full experiment permits original human semantic paths and
embedded metadata, and excludes old model outputs, captions, reference plans,
reports and caches by exact allowlist. The controlled experiment uses pixel
derivatives, opaque names and synthetic capture times; its three repeated images
test selection mechanics, not fixture-wide scene accuracy.

Neither experiment is an independent blind evaluation. A blind judge must start
in a separate clean context with access only to the staged source, new Result,
release contracts/Skills and its declared task. Do not inherit this developer
session, this report, operator mapping, old Result, memory index or filesystem /
search access to those sources. Record separately Tool retrieval, model-visible
content and adopted judgments; input staging alone cannot enforce Host access.

Full fixture runs may finish local evidence and then fail `provider_unavailable`:
the existing Geo acquisition contract is required and this experiment deliberately
provides no map credentials or remote authority. Such a run is not a sealed or
Plan-ready success. Its completed local Work remains measurable and reusable.

Results and source commit are recorded in the [evaluation document](../../../docs/eval/eval-260908-1329-precheck-corrections.md).
Source HEAD: `a9ba4a0908510e8594b1d6afb04dad02f78830c8`, plus uncommitted repairs.
No original fixture file is changed. The session remains working with partial
acceptance: known temporal behavior and installed embedding execution passed;
end-to-end Plan cost/quality and independent evaluation remain unproven.

## Acceptance follow-up

The operator-manifest exclusion now resolves `..` and symlink aliases before
staging, rechecks before writing, walks canonical parents without following
symlinks, and exclusively creates a private output file. It rejects mapping
files inside both the source and judged trees. This protects the path boundary;
it does not isolate arbitrary Agent filesystem/search access or inherited memory.

Repair historical metric references without changing timing, Run, Result or
model execution:

```bash
.venv/bin/python eval/sessions/260908-1329-precheck-corrections/run.py --repair-result-refs --output /tmp/mediasense-controlled-final
```

The repair binds the metric to the retained Run, verifies the registered sealed
Result size, SHA-256 and embedded reference, then updates only summary metadata.
Nine completed-run summaries across three existing experiment directories now
have verified references. Six failed full-run summaries remain `public_result=null`.

The next paired comparison uses exactly the same 2,134 hash-bound manifest media,
human path semantics allowed, no historical answers/caches/GPX/extra RAW. It runs
the corrected implementation with and without embedding. The current three
full-run coordinate sets contain the same 77 query coordinates; their sorted JSON
fingerprint is `0070d98c0a5cf2f45604c7bb4ec5c8164053912e0300acd2de6f0b9b5703ceef`.
One coordinate is `(0,0)` as retained source evidence, not corrected ground truth.
With Google alone the ordinary address+nearby count is 154 and the current
three-attempt ceiling is 462 requests; fees and provider data handling remain
unknown. Second-run reuse must be measured from the journal. No permission or
credential is inferred from the prior audit.

Before starting remote work, obtain provider/model choice, data-egress permission
and budget. Create two independent fresh Plan contexts from the same neutral
task and release contracts/Skills, each seeing only its exact new Result and
allowed media, without this report, old Plan, operator mapping, other arm's
answers, or inherited memory. Neither context knows the variant label or counts
in advance. Restrict filesystem/retrieval at the Host boundary, not by prompt alone.
Do not call an ordinary full-history developer subagent a blind evaluator.

Record source/bundle/entry counts separately from unique media actually shown,
derived images/frames, collage attachments, repeated presentations, model
requests, input/output/cached tokens, elapsed time and unknown fees. Evaluate
scene/event coverage, anomalies, misplaced-time corrections and navigation quality
against declared evidence, not old generated folder names. Identity resolution
alone is not a VLM or map request. Fewer entries without maintained coverage and
observed lower Plan burden is not a success. Until those runs exist, the claim
remains partial acceptance; do not edit the prior failed outcomes into successes.

Daily installation has been updated through the authorized offline install
script. Its Python 3.13 / torch 2.13.0 environment was checked separately from
the earlier Python 3.11 validation: the real MCP encoded nine controlled inputs,
sealed three entry candidates, then reused all nine encodings in a successor
Run. Both Result references are recorded in `metrics/combined.json`. This updates
the executable; it does not silently configure user-level models, map credentials,
or a running Agent session. Full Plan comparison still awaits its external scope.
