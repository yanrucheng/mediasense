---
name: "human-oriented-cli-design"
description: "Designs and reviews human-facing CLI control: orientation, consequences, bounded delegation, truthful outcomes, evidence, recovery, and takeover. Invoke when people operate or supervise work through a CLI; not for machine-readable protocols or textual polish alone."
version: "2.0.0"
activation: "auto"
context-load: "standard"
---

# Human-Oriented CLI Design

Treat a human-facing CLI as a control boundary. A person must be able to understand relevant state and consequences, exercise their authority at an appropriate granularity, verify what actually happened, and recover or take over without reconstructing hidden execution or micromanaging every step.

## When to Use

- Designing or reviewing a CLI through which people inspect, change, authorize, supervise, or recover work.
- Designing onboarding, configuration, authentication, environment selection, mutations, destructive actions, or other CLI behavior where incorrect understanding can change the outcome.
- Designing long-running, asynchronous, cross-session, automated, or Agent-driven work exposed through a CLI.
- Diagnosing cases where people cannot determine what is happening, what was authorized, what changed, whether work is complete, or how to continue safely.
- Defining acceptance evidence for human control through a CLI.

## Boundaries

- Machine-readable CLI protocols, schemas, exit-code taxonomies, structured errors, side-effect declarations, bounded output, and idempotency are outside this Skill; it requires only that human and machine presentations preserve the same material semantics.
- Deep review of visible terminal text, composition, hierarchy, wording, and transcript quality belongs to the `cli-textual-ui-review` skill.
- This Skill defines the human-facing properties of a CLI. It does not define business authorization policy, assign responsibility among Humans, Agents, Skills, and Tools, or prescribe delegation and runtime mechanisms.
- Implementation work is in scope only when the human-facing CLI contract is being designed or judged.

## Required Downstream Product

An acceptable CLI preserves effective human control in every material scenario. Required properties depend on the work's effects, authority, reversibility, duration, uncertainty, recovery cost, and operating conditions.

### Orientation and Continuity

- Make the relevant operation, target, account, environment, scope, and state identifiable as applicable, without requiring source-code inspection or guesswork.
- Distinguish current facts from stale, estimated, cached, or unknown information when the difference could change a decision.
- Give work that can outlive a command, terminal, or session a durable identity and a reliable way to inspect its current state and continuation options.
- Do not require people to remember prior output or execution history in order to resume safely.

### Consequence and Authority

- Before commitment or another material boundary, expose the intended effect, affected scope, required authority, reversibility, and any point after which interruption or rollback is unsafe.
- Bind authorization to the action people actually understood: its goal, target, environment, scope, material plan, and constraints as applicable.
- Treat a material change to that action or its risk as a new decision boundary; do not silently reuse stale approval.
- Make the limits of available authority visible when they affect what may proceed.

### Proportionate Control

- Let bounded, sufficiently authorized work proceed without repeated confirmation or unnecessary interaction.
- Require human involvement when intent, authority, risk tolerance, or an exception cannot be resolved within the delegated boundary.
- Provide intervention appropriate to the work and its reversibility. Preview, approve, reject, modify, pause, resume, cancel, or take over are possible methods, not universal requirements.
- Never promise an unsafe pause, cancellation, rollback, or takeover. Expose the actual point of no return and the available recovery path instead.
- Human-facing confirmation does not replace enforcement at the boundary capable of causing the effect.

### Truthful Execution and Outcomes

- Represent materially different states distinctly, including work that is pending, active, waiting, blocked, partially successful, failed, cancelled, or complete when those states exist.
- Base progress and completion claims on observable execution evidence. Do not present intention, acceptance, process creation, or an Agent's assertion as proof of completion.
- State material uncertainty, unverified results, partial effects, and work that may still be running.
- Explain user-relevant causes and constraints without exposing private reasoning, secrets, or raw internals as the primary interface.

### Evidence, Recovery, and Re-entry

- Provide evidence sufficient to support the reported outcome. When change is possible, identify what changed, what did not, what remains unresolved, and which result or artifact supports the claim.
- Make safe retry, repair, rollback, continuation, or escalation discoverable when one is available; do not invent a recovery action when none exists.
- Preserve the identifiers and state needed to reconnect later to long-running or cross-session work.
- Keep an incomplete or failed operation diagnosable enough that a person can decide whether to retry, change direction, or take over.

### Semantic Integrity Across Presentations

- Human-readable and machine-readable surfaces may present information differently, but they must agree on material state, target, authority, effects, uncertainty, and outcome.
- Preserve decision-relevant meaning in applicable non-TTY, no-color, logging, narrow-display, and assistive-use conditions; presentation enhancements must not become the only carrier of meaning.
- Support novice safety and expert efficiency without forcing every person through the same interaction depth.
- Prefer progressive disclosure over either hiding material facts or displaying all available detail by default.

## Judgment and Evidence

Derive review coverage from the actual human goal and the relations that can change understanding, authority, effects, control, verification, or recovery. Do not require a universal workflow, maturity score, risk ladder, time threshold, command grammar, output order, confirmation mechanism, or report template.

Ground judgments in observed behavior or explicit design inputs. Depending on the surface, useful evidence may include help and status views, transcripts, before-and-after state, authorization boundaries, long-running task records, interruption and re-entry behavior, human and machine representations, or behavior under relevant terminal and logging conditions.

Choose scenarios capable of falsifying the design. Where material, establish that:

- a person can orient on first use and after returning later;
- low-risk work is not obstructed by unnecessary control ceremony;
- work proceeds within a bounded delegation and stops or escalates when that boundary becomes insufficient;
- risk, target, authority, or plan changes create a new decision boundary;
- partial effects, failure, cancellation, and completion match reality;
- recovery or the lack of recovery is discoverable; and
- critical meaning survives each supported presentation used in practice.

Do not claim coverage that the evidence does not support. Mark assumptions and missing evidence when they could change acceptance. Converge when every material property is supported or exposed as a consequential gap; do not continue merely to complete a checklist.

## Review or Design Result

Make the conclusion-bearing structure inspectable. State:

- the human goal, material scenario, and boundary being judged;
- the observed evidence or explicit design assumptions;
- the capability or control failure and its consequence;
- the semantic property the CLI must provide, leaving implementation open unless a mechanism is itself necessary; and
- the evidence that would demonstrate acceptance, including material coverage limits.

Prioritize findings by their effect on understanding, authority, safety, truthfulness, verification, and recovery. Do not substitute a maturity label, polished copy, or checklist completion for proof that people can actually control the work.
