## 1. Govern the Skill boundary

- [x] 1.1 Add the `precheck-agent-workflow` proposal, design, and delta specification without changing existing PreCheck runtime contracts.
- [x] 1.2 Validate the change strictly before implementation and preserve the established Zero BC policy.

## 2. Implement the Skill

- [x] 2.1 Initialize `.agents/skills/mediasense-precheck/` with only `SKILL.md` and `agents/openai.yaml`.
- [x] 2.2 Write concise guidance for data-sensitive initial compression, progressive cost reporting, diagnosis-led revision, Tool-only I/O and state, local-first execution, bounded geocoding confirmation, recovery, honest accounting, and exact Result handoff.
- [x] 2.3 Keep automatic discovery enabled and exclude Plan naming/grouping and Apply filesystem execution in activation metadata.

## 3. Verify behavior

- [x] 3.1 Add deterministic Skill-package, activation-boundary, contract-link, and scenario-coverage tests.
- [x] 3.2 Run independent realistic Agent forward tests for initial compression and cost reporting, diagnosis-led revisions whose observed outputs are 500 then 3 then 200, failures and recovery, online confirmation and skip, partial and blocked Results, exact Plan handoff, and negative activation.
- [x] 3.3 Run skill-creator quick validation, strict OpenSpec validation, repository fast tests, Ruff, format, lock, and `git diff --check` without source-media or online effects.

## 4. Review and close

- [x] 4.1 Present a reviewable report covering responsibility, test evidence, remaining limitations, and exact change scope.
- [x] 4.2 After explicit Human acceptance, archive this OpenSpec change and write the unchanged completion report to the paired delegation result without committing or pushing.
