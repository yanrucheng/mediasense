> 第6包拟议Skill行为；本轮不修改已安装Skill。仅规定持续页面、保存和确认所需的变化，不调整其他问题包或历史设计。主方案见[README](../../README.md)。

## MODIFIED Requirements

### Requirement: Preview drives meaningful revision checkpoints
The Skill SHALL establish or restore Work when planning discussion begins from a usable Result and use the Tool-delivered current page. Before claiming that the plan has changed or requesting review of changed planning content, the Agent SHALL save the relevant current organization, explanation or unresolved implications. The Skill SHALL support notes-only and partial-draft saves before a complete candidate. It SHALL NOT require every chat statement or private reasoning to be recorded, and SHALL NOT make the Agent author HTML, mosaics, page layouts or independent presentation business data.

#### Scenario: Only a partial directory is decided
- **WHEN** the Agent has a supported group for part of scope while other items remain unresolved
- **THEN** it can save a draft and share the automatic page without inventing outcomes for the remainder

#### Scenario: User only browses
- **WHEN** the Human refreshes or expands a directory without changing planning content
- **THEN** neither the Agent nor the page creates a planning revision

#### Scenario: User changes a candidate
- **WHEN** feedback changes important organization or supporting context
- **THEN** the Agent saves the appropriate replacement/draft/withdrawal and uses the new delivered view instead of editing a standalone page

### Requirement: Human confirmation applies to the exact reviewed candidate
The Agent SHALL request whole-Plan acceptance only for an explicitly submitted complete candidate with adequate review delivery, and SHALL provide its Tool-returned revision-specific entry. It SHALL preserve the Human's actual acceptance scope in the existing trusted local-client boundary, binding Work, reviewed revision and candidate identity. It SHALL NOT infer acceptance from page visits, local feedback or notes. Any new accepted planning update, including a notes-only or same-value save, SHALL invalidate the old revision binding. After valid acceptance the Agent SHALL seal that exact version without first creating an unnecessary confirmation-note revision.

#### Scenario: Human accepts and no planning update occurs
- **WHEN** the Human explicitly accepts the presented revision and it remains current
- **THEN** the Agent can request seal using its exact Tool identities and matching trusted context, without another popup or digest recital

#### Scenario: Notes change after acceptance
- **WHEN** the Agent saves any new working-note revision after that acceptance
- **THEN** it requests review/acceptance of the new revision before seal even if the candidate identity is unchanged

#### Scenario: Human asks to wait
- **WHEN** the Human withdraws acceptance before seal
- **THEN** the Agent stops sealing and saves an appropriate withdrawal or draft state; it does not reuse the earlier statement merely because directory bytes are unchanged

## ADDED Requirements

### Requirement: Delivery failure is reported without false completion
The Skill SHALL distinguish successful planning persistence, actual page availability, evidence sufficiency, complete organization and Human acceptance. It SHALL use state-only inspect or safe replay to recover known committed work after delivery failure. It SHALL NOT report complete HTML delivery merely because a path or renderer object exists, and SHALL NOT work around a broken delivery path by hand-authoring production HTML.

#### Scenario: View is unavailable after a successful save
- **WHEN** the operation receipt reports the saved revision but view is unavailable
- **THEN** the Agent states both facts and pursues Tool-level recovery while preserving the saved work

### Requirement: Behavior evaluation checks ordinary Agent usage
Acceptance SHALL include actual installed Tool entry, real browser navigation and representative independent Agent execution. It SHALL check that the Agent handles drafts, changes and final acceptance using delivered entries without writing frontend code or duplicated display content. A claim about less capable Agents SHALL be supported by evaluation using the selected models, not inferred from GPT-6 or deterministic tests alone.

#### Scenario: Agent completes the review loop
- **WHEN** an evaluation Agent starts with the installed Skill and a supported synthetic Result
- **THEN** its real trace shows save, delivered page, feedback, revision and matching final binding without manually generated HTML
