---
id: "geo-query"
title: "MediaSense Geo Query Tool Contract"
type: spec
status: active
created: 2026-08-30
updated: 2026-09-09
timezone: "Asia/Shanghai"
parent: "index-contract"
depends-on:
  - "design-260830-1527-reusable-capability-architecture"
  - "design-260830-1626-geo-capability-evolution"
superseded-by: ""
---

# MediaSense Geo Query Tool Contract

本页位于稳定合约目录。当前规范以此处为准；迁移到此目录本身不构成新的实现或真实数据验收。


## Purpose and status

`mediasense.geo.query` returns challengeable geographic candidate observations for
exact coordinates. It offers a high-level `resolve_place` operation and bounded
`reverse_geocode` and `nearby_places` operations without transferring stage
selection, Plan interpretation, or Human authorization into the Tool.

This is the active, stage-neutral Geo Tool contract. PreCheck calls it after local
media-aware compression and owns the resulting per-Source-Item Result projection.
A Plan Agent may call it directly for bounded investigation when prepared evidence
needs scrutiny. The Tool does not own either stage's selection, interpretation, or
handoff state.

## Operations

| Operation | Purpose | Does not decide |
| --- | --- | --- |
| `resolve_place` | Obtain the least expansive useful place candidate and applicable continuations; when both nearby bounds are supplied, obtain address and bounded nearby-place components in the same authorized request | Final location, album name, grouping, or evidence sufficiency |
| `reverse_geocode` | Inspect normalized address and administrative components | Whether the address is the intended venue |
| `nearby_places` | Inspect bounded nearby-place candidates | Which candidate is correct or worth using |

Lower-level operations remain provider-neutral. They do not expose raw HTTP,
coordinate-conversion algorithms, AMap fields, or Google fields.

An unbounded `resolve_place` keeps the progressive default and returns a separately
authorizable nearby-place continuation. Supplying both `radius_meters` and
`max_places` explicitly expands that same operation: the request fingerprint and
effect envelope then cover both address and nearby-place acquisition. A Provider
may satisfy both components with one external request when its API returns them
together; separate Provider requests remain separately counted. The supplied
radius and result count are hard upper bounds. A versioned Provider profile may
use a narrower effective radius or result count, but never exceed the authorized
bounds.

For the current adapters, one execute attempt costs at most one AMap request
or two Google requests per expanded coordinate. The immutable retry policy allows
at most three execute attempts per Provider. When both Providers are authorized,
the request-wide ceiling reserves at most nine Provider requests per logical
coordinate; actual effects count requests that were sent. A single
Provider request that supplies both components is recorded as a `resolve_place`
attempt, while the returned evidence remains two separately statused components.

## Authorization and effects

Without matching trusted authority, an effectful request returns
`authorization_required` and performs zero provider requests. The proposed
authorization binds:

- exact normalized subjects and coordinates;
- operation, locale, and route context;
- transmitted data classes;
- allowed providers and fallback;
- logical-query, provider-request, and billable-unit ceilings; and
- retention scope.

Changing any bound dimension invalidates the authorization. A continuation reuses
subject identity and prior evidence but does not inherit permission for a larger
effect.

Subject order is not part of the canonical effect identity. Each coordinate in a
batch begins from the request's route context, so inserting or reordering another
coordinate cannot silently alter its Provider/language semantics.

Missing authority and non-matching authority are distinct but both effect-free.
Missing authority returns `authorization_required`; non-matching authority returns
the same actionable outcome with an `authorization_mismatch` qualification and a
fresh proposed envelope. A Human refusal is not inferred by this Tool: the calling
stage records that decision and stops before invocation.

Only coordinates, datum, locale, and provider-required lookup controls may cross
the provider boundary. Media, renditions, embeddings, prompts, paths, filenames,
captions, and general metadata are rejected before network access.

Every coordinate supplies `datum` explicitly. Required references and locales must
contain a non-whitespace character. Neither JSON Schema `default` annotations nor
runtime parsing silently supply a missing datum.

## Result meaning

Results distinguish `success`, `partial`, `no_result`,
`authorization_required`, `unavailable`, `failed`, `indeterminate`, and
`cancelled`. Each requested evidence component separately distinguishes
`success`, `no_result`, `failed`, `indeterminate`, and `not_requested`.

The result reports logical queries, observed provider requests, billable units or
`null` when unknown, transmitted data classes, provider attempts, coordinate datum,
fallback, qualifications, and applicable continuations. Provider candidates remain
observations; absence means no candidate was returned under this request, not that
no place exists.

## Replay and lifecycle

An effectful request is admitted to a Tool-owned journal before provider access.
Once admitted, an identical `request_id` and effective request returns the recorded
terminal result without another authorization prompt or Provider request. If a
caller also supplies authority it must match the original binding; changed input
or explicit conflicting authority is an error. If completion cannot be
established, replay remains `indeterminate` and does not automatically repeat the
effect.

The journal is execution evidence, not a shared geographic cache or place-truth
store. Callers own retention and projection of accepted observations.

## Provider replacement

AMap, Google Maps, or another adapter may be selected within the authorized
envelope. Compatible replacement preserves normalized operation meaning,
authorization enforcement, outcome distinctions, provenance, request accounting,
and continuation behavior. Provider order, routing algorithms, transport, and
coordinate-conversion methods are not permanent contract.

## Files

- [`geo-query.tool.json`](geo-query.tool.json) — callable input and output contract.
- [`geo-query.mock.json`](geo-query.mock.json) — authorization-required,
  authorization-mismatch, success, partial, and continuation examples.

## PreCheck 证据交付边界

本轮保留 Geo Tool 的操作、授权、效果上限和幂等语义。PreCheck 如何构造采集单元、选择查询点以及复用到源项，是其 stage adapter 的可替换方法；现有策略的迁移质量仍须核对，合约定稿不等于对该策略验收。

Read 保留真实查询坐标、观察时间、有效 profile、请求的附近范围与数量，以及已知的实际缩窄/投影限制。两个组件分别交代，不因一个成功就伪造另一个成功。候选距离相对查询点，不能冒充离每个复用源坐标的距离。未返回的有效范围保持未知，不从请求上限推出穷尽查找。

Plan 可以在自己的授权范围内调用同一 Tool 补查，保留新调用来源与候选。新证据不能改写或冒充原 PreCheck Result；Human 的地点确认也不成为 provider 观测。该边界不要求新增 Geo Tool、模型或缓存服务。


### D6. 有限重试归 Tool，费用预先受限

共享 GeoCapability 接受内部不可变 RetryPolicy（配置值，不是新公开字段/Tool）。
本轮实现策略：每坐标、每候选 Provider 最多3次 execute，瞬态失败后等待1秒、3秒；
每坐标单调时钟120秒墙钟预算，每个实际 HTTP timeout 不超过剩余时间及原 Provider timeout。
成功组件保留，no_result 不在同 Provider 重试；只有 transient(限流/服务5xx/安全可重试网络错误)重试。
permanent 不重试；indeterminate 立即停止。回退按现有已授权 Provider 路由，不新增 Provider。
“安全可重试网络错误”只包括证明请求未发送的连接失败；发送后的timeout/未知完成仍按现有
Geo契约归indeterminate，不能把计费未知当作可盲重试失败。HTTP已响应的429/5xx可重试，
其请求数照实记录；认证/参数等永久错误立即终结。GeoProvider.execute增加内部deadline及cancelled
参数，所有真实adapter与fake遵守同一端口；每个HTTP admission前重新校验剩余deadline。
扩展操作一次可有两次 HTTP，全部受 Provider 声明 ceiling；重试会重复读已成功组件时照实计费，
不丢失已得候选。Sleep 可取消，deadline或额度耗尽时终结带具体 qualification 的失败。

预检请求 ceiling = coordinates × sum(provider.execute ceiling × max_attempts)，已知 billable
ceiling同样上界；配置策略描述加入有效请求 fingerprint 与 journal admission identity并随披露返回。
纯 request 数据保持现有 Geo公共输入，Host/Tool 以 request+effective profile 的 canonical值计算最终
fingerprint，不让客户端自行猜摘要。变更策略使旧授权不匹配；较小的既有授权不能被扩大，
不足以再发一次时直接终结。效果最终失败后的相同 request_id 重放只读 journal，不重做外部调用。
失败证明与安全重试资格由adapter返回的attempt/error类别决定；缺分类默认不可重试，不能靠自由message猜测。
PreCheck 外层 Work 不重复重试已经终结的 Geo失败，只有未发送且可安全恢复的工作走本地恢复。
