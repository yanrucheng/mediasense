---
name: mediasense
description: "Sets up, verifies, and enters MediaSense, then routes work to PreCheck, Plan, or Apply from the user's intent and exact retained state. Use when a user is installing or configuring MediaSense, starting without knowing a stage, continuing prior MediaSense work, or diagnosing why MediaSense is unavailable; not for replacing stage-specific judgment or Tool guarantees."
---

# MediaSense

Bring one Human-selected Honeycomb from unknown readiness to a verified
MediaSense integration, then route the user's work to the stage that owns it.
Keep product setup and cross-stage orientation here; keep PreCheck, Plan, and
Apply semantics in their independently loadable Skills.

## Establish readiness

This Skill set targets the MediaSense `0.11.x` CLI and its bundled Tool contracts.
For installation, upgrade, repair, or unknown readiness, read the
[installation and upgrade runbook](references/installation.md) before changing
state. It is the offline release snapshot of the single authoring source,
`readme/installation.md` in the MediaSense repository. Use the selected target
release's verified snapshot for an upgrade; do not combine instructions from
unidentified builds. If the reference is missing, repair the incomplete Skill
from the trusted release before proceeding.

The runbook owns setup checkpoints, exact build verification, dependency and Skill
manager handling, project connection, rollback, and evidence. This entry owns
finding that procedure and routing business work. Apply the user's existing
choices and authorization; a request to review a runbook is not authorization to
switch the actual installation.

If the exact intended installation and project Skills are already verified and
the current Agent session has loaded the matching Host/contracts, continue without
repeating setup. Tool names or version strings alone do not establish that match.
A separately launched diagnostic Host cannot prove what this session loaded.

## Route to the owning stage

Route from the user's goal and exact public references. Do not infer progress
from private databases, caches, directory names, or the mere presence of files.

- Use `mediasense-precheck` when the user has a source path to prepare, needs to
  open a Dataset, has no Plan-ready Result, or must revise upstream evidence.
- Use `mediasense-plan` when the user has one exact Plan-ready `result_ref` and
  needs grouping, naming, inspection, revision, confirmation, or a Frozen Plan.
- Use `mediasense-apply` when the user has one exact Frozen Plan and wants to
  prepare, authorize, execute, recover, inspect, or rewind filesystem effects.
- If the requested continuation lacks the required exact reference, explain
  what is missing and use the owning stage's public read or status operation
  when available. Do not silently restart from PreCheck or reconstruct state.

Once routed, follow the selected stage Skill rather than reproducing its method
here. A stage handoff changes the active method, not the authority of its Result,
Frozen Plan, Receipt, Human confirmation, or Tool response.

## Boundaries

- Loading this Skill grants no authority to install software, edit Agent
  configuration, enable network providers, spend money, or change media.
- Keep executable installation, Honeycomb-local Skill installation, client MCP
  configuration, and Dataset state as independent locations and effects.
- Do not perform PreCheck interpretation, Plan decisions, or Apply filesystem
  execution in this entry Skill.
- Report package, machine installation, and current-session readiness at their
  verified scopes as the runbook requires. Do not claim stage completion without
  its authoritative artifact.
