---
id: "geo-query"
title: "MediaSense Geo Query Tool Contract"
type: spec
status: active
created: 2026-08-30
updated: 2026-09-10
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
`authorization_required`, `unavailable`, `failed`, `indeterminate`, `blocked`, and
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
or explicit conflicting authority is an error. Replay never sends a provider
request. For a retained v2 cycle, the same scope and recovery linkage replay its
original effective profile even if the Host configuration has changed; replay does
not authorize execution under the new configuration. Reusing one consumed trusted
authorization under another request ID is refused. After the execution owner has stopped, retained per-request checkpoints
may establish completed components and close the interrupted execution. A reserved
request without a saved response remains indeterminate; absence of a response
never proves zero effects. A live owner returns `execution_in_progress`.

Recovery is a separate, explicitly authorized request on this same Tool. It has a
new `request_id` and `recovery: {prior_request_id, result_digest}`. The digest is
SHA-256 of the exact prior response encoded as UTF-8 JSON with sorted object keys,
no insignificant whitespace and unescaped Unicode. Query scope, bounds, subject
identities and the original cumulative envelope remain unchanged. Only one
successor may own each prior response. Replaying a successor returns that
successor's saved result; it never opens another retry cycle. Unknown or changed
references return `request_not_found` / `recovery_stale`; an unclosed or unbounded
historical execution returns `recovery_unavailable`.

Each recovery response carries cumulative attempts and effects, while previously
completed responses remain immutable. Component observed_at retains the original
acquisition time; attempts carry execution_request_id and observed_at when proven,
so a successor does not relabel historical requests as new effects. Successful and valid no-result components
are retained; only missing components may be requested again. Another bounded
cycle requires fresh trusted authorization tied to the successor and current
execution profile. Unknown charges remain unknown after successful recovery.
Cumulative ceilings do not reset with request identity, process restart or replay.
Recovery responses expose the root/prior identity, prior known or bounded request
usage, prior billable knowledge, cumulative ceiling and remaining request budget;
trusted confirmation displays these together with the exact request and network profile.
A ceiling that cannot admit another request blocks execution; this recovery form
does not silently increase it.

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


### D6. 有限执行、目标地域和公开恢复

目标地域决定服务适用性，执行机器的所在地或连通性不决定素材地域。内地目标优先适合内地地址及 POI 的高德；海外目标需要当地适用服务。港澳、边界附近及无法可靠判断的输入不得用内地粗框伪判。地域依据应能离线取得、可追溯，不能先请求 Google 判国家，也不能把能连通的高德自动当作海外替代服务。

有限执行由共享 Geo Tool 负责。现行周期上限为每坐标、每适用 Provider 三次尝试，退避 1/3 秒，每坐标 120 秒；HTTP timeout 不超过剩余窗口。已获得成功和有效 no_result 组件保留，支持独立组件的 Provider 只补欠缺组件。复合 API 不得因重复读取而覆盖原成功，每次实际请求仍计数。

证明未发送的连接失败以及已响应的暂态服务错误可以有限重试。发送完成未知保持 indeterminate；只有声明可重复查询语义、具有已分类暂态传输原因、并处于明确授权及累计预算内的 Provider/operation，才可再尝试。旧记录的通用错误不能升级成已证明的网络原因。原未知效果和费用不会因下一次成功变成零。未经声明的 operation、TLS/鉴权/配额故障不得套用通用未知重试。

有效服务的明确地点级失败可以局部终结，后续项继续。适用服务持续不可达、鉴权或配置前提缺失、超时窗口或累计预算耗尽时返回 blocked，保存成功组件及后续 not_requested，停止对余下地点重复发送。海外适用服务不可达且无适用替代时，需要用户提供 Proxy、调整网络或作其它明确决定；不能自动降为整批缺地点并封存 Result。blocked 表示本周期已停止执行且有可解释的外部条件，不代替未知实现异常。

当前 Provider 请求上界由逻辑坐标数、适用 Provider 和有限重试 ceiling 决定；预算同时覆盖首次尝试、重试和恢复。逐请求预留必须先于发送持久化，确定未发送可释放请求占用，未知发送保留占用。对中断后只有预留证明的 attempt，`request_count_kind=reserved_upper_bound` 明确其 provider_requests 是预算占用上界；不能当作精确已发送次数。无法证明转换后的坐标时 provider_coordinate 为 null。累计实际请求数不明时 effects.provider_requests=null，以 provider_requests_upper_bound 交代保守上界，billable_units 保留未知。正常 attempt 省略 request_count_kind 时含义为 exact。

执行策略及网络 profile 参与授权指纹。execution_profile 只披露脱敏代理接收位置、配置身份、CA 来源和时间限制；不暴露密钥、代理密码或原始传输 URL，也不以已配置声称网络可达。新增或改变代理会使旧确认不匹配，需要针对新的实际接收边界明确确认。不会自动设置代理或关闭 TLS 验证。

PreCheck 通过既有 status/confirmation/resume 入口恢复：先说明阻塞和累计已用效果；用户处理条件后 resume，完整披露只补欠缺组件的范围及原累计上限，再按明确 proceed 执行。恢复 journal 先提交、Work 后幂等投影；投影失败重放本地结果，不重复发请求。状态读取本身不探测地图。取消不生成假完成 Result，旧 Result 不改写。

旧 journal 只有在原授权绑定、范围和累计消耗可证明时才可衔接恢复；未知上界不能猜成剩余额度。升级 Geo journal 的内部版本不提升无关 Dataset、Work 或 Result 格式。新存储须拒绝旧 Host 写入，包括迁移前已打开但不支持新写入协议的连接。

### 当前生产路由与资源

生产路由使用随发行包提供的 Natural Earth 5.1.1 WGS84 几何及源码中的校验身份；资源出处与许可见包内 geo/NOTICE.md。内地使用高德，海外（包括本策略中的港澳、台湾查询范围）使用 Google。地域标签只决定本次服务路线，不是地点法律归属事实。GCJ02 输入先经既有转换器归一到 WGS84。距内地几何边界/海岸 500 米以内返回 uncertain；该保守带不是数据精度保证，填海、岛屿及争议范围仍需更好证据。

routing 交代坐标、region、当前可用 provider_order、required_provider 及离线 basis；preferred_provider 不能覆盖适用性。混合批次按各坐标独立判定，顺序不改变授权身份。批次中有无法确定路线或缺少适用 Provider 的待查询坐标时，预检零效果返回 unavailable；先解决条件后再确认。已取得的组件在恢复时复用，不因当前路线资源改变而重新查询。暂不实现用自由文本臆定地域或通过不适用服务填满 Result。

恢复调用顺序：blocked 时发送 `resume` 且省略 decision，准备恢复确认；进入 paused 并取得完整 confirmation 后，才发送 `resume + decision=proceed` 触发可信确认。前一步不授予新的外部效果，不能把尚无披露时的 proceed 当作授权。
