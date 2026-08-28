---
id: "spec-260827-1138-frozen-plan"
title: "MediaSense Frozen Organization Plan Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-08-28
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
  - "spec-260826-1546-precheck-read"
  - "clarify-260827-0107-plan-frozen-contract"
superseded-by: ""
tags: ["mediasense", "plan", "frozen-plan", "contract"]
---

# MediaSense Frozen Organization Plan Contract

## Decision

A Frozen Organization Plan is the immutable, user-confirmed organization result produced from one exact PreCheck Result. It preserves a compact but mechanically complete logical organization; it is not a per-file ledger, Plan working state, Apply authorization, or execution log.

Its primary business value is to let a user review and correct compressed organization decisions before an irreversible or high-loss filesystem change. Preview and regenerable output may use a lighter workflow. A dangerous Apply requires a conforming Frozen Plan plus separate authorization.

[`frozen-plan.schema.json`](frozen-plan.schema.json) is the machine-readable minimum shape. [`hong-kong.mock.json`](hong-kong.mock.json) is a human-authored reference wrapper whose `frozen_plan` member conforms to that schema. Its five-item scope combines one complete three-item `represents` relationship with two explicit anomalous Source Items, all reachable through the current PreCheck development Mock. It is not runtime output, a claim of actual user confirmation, or Apply authorization.

No Plan read Tool is defined. Unlike a potentially large PreCheck Result, a Frozen Plan is intended to be a complete sealed artifact consumed deterministically. A read interface requires separate scale or storage evidence.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

The earlier seven-item YAML and all draft field names are review evidence only. Compatibility aliases, adapters, deprecated fields, and dual representations are prohibited.

## Stable meaning

The contract fixes five responsibilities:

1. **Exact upstream binding.** One Frozen Plan binds one exact immutable `result_ref`. Dataset identity is obtained through that Result rather than repeated as a second authority.
2. **Compact authoritative scope.** The Plan independently states the exact Result-local set it promises to organize. The scope may reuse sealed `accounts_for` or `represents` relations, combine them, and subtract small explicit exceptions; it does not copy every member merely to claim completeness.
3. **Final logical organization.** The Plan fixes logical root and relative group paths, group membership, and source-name decisions. These are organization semantics, not copy, move, link, or syscall choices.
4. **Other accounted outcomes.** Every in-scope source-media item either has a logical home or an explicit other outcome. Retaining current organization is complete; exclusion requires a concrete reason. Silence never means “ignore”.
5. **Immutable confirmation.** A final user confirmation binds the digest of the complete sealed content. Any semantic change creates another Frozen Plan.

Organization methods remain open. The contract does not prescribe how the Agent inspects Evidence, decides whether to ask the user, or chooses to continue Plan work versus reopening PreCheck. If the final result binds a different PreCheck Result, it is a different Frozen Plan.

## Compact source sets

A source-set expression resolves only within the bound Result. The same expression language is used for the authoritative Plan scope and for final outcomes, but those uses have different responsibilities: scope states who the Plan promises to handle; outcomes state what happens to them.

- `precheck_relation` reuses the Result's sealed outbound `accounts_for` or an Evidence object's sealed outbound `represents` relation;
- `explicit` names a small exact set of Result-local Source Items;
- `union` combines sets;
- `difference` subtracts a fixed set, normally for a small exception.

Natural-language selection is invalid. Apply must never reclassify media to decide membership. Large corrections to a poor PreCheck compression should normally produce a better Result instead of accumulating a large patch language in Plan; this is a quality rule, not a prescribed Planning Agent workflow.

## Logical organization

`logical_root` and each group's `relative_path` define the confirmed logical tree. The concrete parent directory, mounted volume, and filesystem are selected and verified by later Apply authorization.

A group is necessary only where the final organization contains that grouping. The schema does not require every accounted outcome to become a group and does not define a separate Placement or Target Object entity.

Each group selects members through one compact source set. Source names are preserved by default; explicit overrides capture the exceptional name decisions that Plan must not leave to Apply.

All first-profile outcomes are disjoint. Deliberate multiple logical homes have not been demonstrated by a reviewed use case and are therefore outside this profile rather than represented by an unused exception mechanism.

## Other outcomes and decision notes

For a Frozen Plan eligible for dangerous Apply, every in-scope source-media item must be accounted for. Keeping an item in its current logical organization is a complete `other_outcome` and does not require an exceptional reason. Auxiliary objects, irrecoverably damaged media, or other justified exceptions may be excluded from the logical tree only with a concrete reason.

Normal groups retain only the final organization. `decision_notes` are reserved for exceptions, easily misunderstood decisions, or decisions that received special user attention. They carry the shortest useful explanation and exact Evidence references; complete reasoning, rejected candidates, queries, model payloads, and copied Evidence do not belong here.

## Apply boundary

The Frozen Plan does not choose copy, move, hard link, symlink, batching, temporary paths, filesystem calls, or recovery order. It also does not contain Apply authorization, journal, receipt, actual-operation mapping, performance policy, or rewind implementation.

Apply owns safe materialization, current absolute destination binding, efficiency, integrity verification, and short-window recovery. It must preserve the Frozen Plan's logical root, relative structure, membership, names, and accounted exceptions without adding semantic decisions.

## Seal and confirmation

The envelope contains `sealed_content` and `seal` rather than a mutable `state: frozen` flag. The stable semantic requirement is that final confirmation bind the exact complete content. Canonicalization and digest choice are an encoding profile, not permanent product semantics.

The first encoding profile is `mediasense-json-strings-sha256-v1`. The schema intentionally permits only objects, arrays, and strings inside `sealed_content`; numbers, booleans, and null are outside this profile.

1. serialize JSON with no insignificant whitespace, preserve array order, sort object keys by Unicode code point, use the shortest required JSON escapes, and encode unescaped non-ASCII text as UTF-8 without Unicode normalization;
2. compute SHA-256 over those UTF-8 bytes and prefix the lowercase hexadecimal value with `sha256:`;
3. match that value to `seal.content_identity`;
4. bind the final confirmation to the same identity; the `plan_ref` is already covered by that identified content.

Future profiles require explicit contract review and profile identifiers. [`tests/test_frozen_plan_contract.py`](../../../tests/test_frozen_plan_contract.py) carries independent canonical-text vectors and the current Mock digest vector for the first profile.

The contract records which content was confirmed. Identity-provider authentication and the user interaction used to obtain confirmation are outside this artifact contract.

## Semantic conformance

JSON Schema validates shape. A conforming sealer or validator must additionally resolve the bound Result and prove all of the following:

- every source-set expression resolves successfully and only to Source Items inside the exact Result;
- the authoritative Plan scope resolves completely and is nonempty;
- logical-group members and other outcomes are disjoint and their union equals the scope exactly;
- no outcome covers an item outside the scope and no scoped item lacks an outcome;
- no item is both logically organized and assigned an incompatible other outcome;
- logical-group memberships are disjoint;
- logical group paths are unique, relative, and collision-free after applying source-name overrides;
- exception reasons and referenced Evidence resolve inside the bound Result;
- `decision_notes` refer only to in-scope items and Result-local Evidence;
- the final confirmation and digest satisfy the seal rules above.

Failure of any proof means no Frozen Plan is produced. A boolean `complete` or `frozen` assertion cannot substitute for these checks.

## Lifecycle and replacement

Plan Working State is mutable and is not an instance of this contract. Sealing creates a new Frozen Plan. A user change to membership, grouping, names, logical structure, exceptions, or other organization semantics creates another `plan_ref`; the old artifact remains unchanged.

The Frozen Plan, its exact bound PreCheck Result, and every Result-local relationship referenced by its source-set expressions must remain available and immutable through Apply completion, verification, and the configured short recovery window. Apply may not start if any referenced set cannot be completely resolved. Longer archive, comparison, and replay policies are not promised here.
