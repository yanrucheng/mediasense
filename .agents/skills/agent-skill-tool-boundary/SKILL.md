---
name: "agent-skill-tool-boundary"
description: "Allocates responsibility, authority, state, effects, and guarantees across Humans, Agents, Skills, and Tools. Invoke when designing or reviewing agentic architecture, decomposing mixed capabilities, or diagnosing ambiguous ownership, unsafe delegation, or unobservable execution."
version: "3.0.0"
activation: "auto"
context-load: "light"
channels: [public]
---

# Agent / Skill / Tool Responsibility Boundaries

Design agentic systems so every material responsibility, decision right, state transition, effect, and guarantee has an explicit owner. Classify responsibilities, not whole features or deployment units: one capability may legitimately combine Human, Agent, Skill, and Tool responsibilities.

## When to Use

- Placing new functionality in an agentic system.
- Reviewing unclear ownership, hidden authority, unsafe effects, or unobservable failures.
- Decomposing a component that mixes intent, expertise, judgment, execution, and state.
- Deciding whether a reusable capability needs a Tool, a Skill, an Agent, or a composition of them.

## When Not to Use

- Deciding whether a proposed entity is necessary in the first place.
- Designing Skill content, activation, or loading quality.
- Designing a CLI or other concrete interface after its responsibilities are settled.
- Defining project-specific policy, implementation details, or framework-specific runtime mechanics.

## Responsibility Model

| Role | Owns |
|---|---|
| **Human or governing authority** | Goals, authorization, value trade-offs, policy exceptions, and acceptance of consequential risk that has not already been delegated. |
| **Agent** | Interpreting intent, choosing and adapting strategy, applying context, maintaining semantic task continuity, and deciding when to proceed, stop, or escalate within delegated authority. |
| **Skill** | Reusable, domain-scoped knowledge, criteria, constraints, and procedures that should be loaded or updated independently of a particular task or general model capability. |
| **Tool** | A callable capability boundary that performs or exposes bounded work and reports its effects and results under an explicit contract. |

These are logical responsibilities, not mandatory processes, services, or deployment boundaries. A Tool may be implemented with a model or Agent; an Agent may expose itself through a Tool interface; one component may carry several roles. Keep the responsibilities and their authority distinguishable even when the implementation combines them.

Runtime infrastructure may persist state, schedule work, retry, lock resources, pause, or resume execution. It is not a fifth layer. Treat those behaviors as implementation mechanisms and assign their guarantees to the responsible interface or component.

## Allocate Responsibility and Authority

For each material path through the capability, establish:

- the intended outcome and whose intent is authoritative;
- the domain criteria used and where their authority lives;
- who may decide, under what delegation, and when escalation is required;
- what reads, computations, external effects, and state transitions can occur;
- which state matters, who owns its meaning, and what persists across calls or tasks;
- what the execution boundary guarantees about lifecycle, retries, cancellation, concurrency, and failure;
- how uncertainty, partial success, and unsupported cases are reported; and
- what evidence lets the caller determine whether the result is acceptable.

Do not force a mixed capability into one role. Split its responsibilities only as far as needed to make authority, effects, guarantees, and evidence honest. Prefer an existing component when it can own an added responsibility without divided authority or a misleading contract.

## Role Contracts

### Human or Governing Authority

- Human confirmation is required when authority has not already been delegated or when the responsible policy reserves the decision for a Human.
- Standing policy or explicit delegation may authorize a Tool or Agent to make and execute local decisions without repeated confirmation.
- No Agent, Skill, Tool, or runtime mechanism may silently widen that authority.

### Agent

- Preserve the caller's goal, constraints, and delegated authority while selecting or adapting strategy.
- Distinguish evidence from instructions and domain criteria from current task judgment.
- Surface material uncertainty and escalate when authority, evidence, or recoverability is insufficient.
- Do not reproduce a capability already available behind an adequate Tool contract merely to keep it inside model reasoning.

### Skill

- Retain expertise whose independent loading or update materially improves selection, judgment, action, boundaries, or result quality.
- State or point to the authority for consequential criteria; do not become the source of project state, user consent, or runtime truth.
- A Skill may contain principles, decision criteria, constraints, or necessary procedures. Loading it does not itself authorize or execute an effect.

### Tool

- Declare the callable capability, accepted inputs, results, effects, required authority, relevant state, lifecycle, failure modes, and observable evidence.
- Report what actually happened, including partial effects, uncertainty, provenance, and limitations when material.
- Enforce delegated limits at or before the boundary that can cause the effect.
- A Tool may be deterministic or probabilistic, stateless or stateful, immediate or long-running, informational or advisory, and simple or internally agentic. These properties shape its contract; they do not disqualify it from being a Tool.
- A Tool may recommend, decide, or act within explicit delegated policy. It must not present an estimate as a guarantee or make the implementation's confidence the source of authority.

## Composition Invariants

- Reusable criteria may guide a decision, but only an authorized decision owner can accept the resulting trade-off.
- Hard constraints require an executable control capable of preventing the prohibited effect; the control does not thereby own the policy.
- State storage and state meaning are separate responsibilities. A runtime may store state while an Agent, Tool, Human, or external authority owns its semantics.
- Compatible implementation replacement must preserve promised semantics, authority, effects, and evidence. It need not eliminate all integration change.
- Uncertainty must be handled according to consequence and delegated authority, not a universal confidence threshold.
- Add another Agent only when a distinct goal, authority, context, or lifecycle needs its own reasoning responsibility.

## Required Downstream Result

Produce an allocation or review that makes the conclusion-bearing structure inspectable. It must:

- identify the material responsibilities and their boundaries;
- assign each responsibility and decision right to an owner, separating shared responsibilities rather than naming joint ownership vaguely;
- state the authority basis and escalation boundary for consequential decisions;
- define the effects, state, guarantees, uncertainty, and evidence at each callable boundary;
- expose gaps, conflicts, and assumptions that could change the architecture or required action; and
- recommend decomposition or consolidation only where it improves the honesty of those boundaries.

The result is acceptable when a competent reviewer can determine, for every material path: who decides, from what authority and criteria, what may change, who performs the effect, what state and lifecycle matter, what is guaranteed, what remains uncertain, what evidence reports the outcome, and when Human escalation is required.

Leave the investigation sequence, notation, deployment topology, framework, orchestration pattern, and implementation method open.
