---
id: "model-260913-1408-precheck-basics"
title: "PreCheck 基础概念模型：阶段、Run、Result 与 Profile"
type: model
status: active
created: 2026-09-13
updated: 2026-09-14
timezone: "Asia/Shanghai"
parent: "index-model"
depends-on:
  - "design-260823-1918-mediasense-foundation"
superseded-by: ""
tags: ["precheck", "concept-model", "run", "result", "profile"]
---

# PreCheck 基础概念模型：阶段、Run、Result 与 Profile

## 状态与范围

2026-09-13，用户确认本页的基础概念、关系和实例变化规则，第一部分模型建模完成。普通 Run 与局部准备的对外 Contract 已按本模型落实；实现与隔离验收另见下方实施路线，不改变本页已确认的概念。

本页只回答：PreCheck 有哪些概念，它们属于什么种类，实例如何产生，以及修改是否需要增加新的概念。核心模型与依照它形成的代码和契约保持业务无关。

[Foundation](../design/design-260823-1918-mediasense-foundation.md)拥有阶段目的与不变约束；本页拥有 PreCheck 的阶段、运行实例、结果和配置值之间的基础关系。[压缩模型](../design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)另行负责 Result 内部的对象、属性和关系。

## 概念种类

```text
PreCheck〔阶段〕
└── Run〔这个阶段的一次运行实例〕
    ├── Profile〔本次运行使用的处理配置值〕
    └── 产生 Result〔这次运行发布的结果〕
```

树表示概念关系，不是文件目录或内部执行步骤。

| 概念 | 种类 | 含义 |
| --- | --- | --- |
| PreCheck | 阶段 | 产品中负责准备的阶段 |
| Run | 运行实例 | PreCheck 的一次运行，有自己的身份 |
| Result | 结果 | 某次 Run 发布的成果，有自己的身份；发布后保持不变 |
| Profile | 配置值 | Run 使用的处理配置，不因存在而需要独立实体或生命周期 |

本页的 Profile 指 Processing Profile。不同 Run 可以使用相同配置值；配置相同不表示它们是同一次运行。Plan 的组织 Profile 属于另一层含义，不进入这张 PreCheck 主图。

## 修改产生新的 Run 实例

```text
PreCheck
├── Run A
│   ├── profile = P1
│   └── 产生 Result A
├── Run B
│   ├── profile = P2
│   └── 产生 Result B
└── Run C
    ├── profile = P2
    └── 产生 Result C
```

修改要求后再次运行，创建另一个普通 Run。增加的是实例数量，概念种类没有增加。Run B 可以参考 Result A，但这种关联不使 Run B 成为 Run A 的子运行。

本模型不为“修改已有结果”建立 Subrun、子 Run 或其他独立运行种类。新 Run 怎样复用以前的工作，由后续契约和实现解决。

## 实例变化规则

| 行为 | 模型中的变化 |
| --- | --- |
| 开始一次运行 | 创建一个 Run |
| 继续被中断的运行 | 继续原 Run |
| 改变要求后再次运行 | 创建新的 Run |
| 运行发布成果 | 产生 Result |
| 改变已发布的成果 | 由新 Run 产生新的 Result，原 Result 不变 |

Run 可以尚未产生 Result，也可能因失败而没有 Result。正常的一次成功发布对应一份 Result；重试同一次发布不意味着另一个结果。

## 与后续工作的边界

计算能力、缓存、调度和存储属于实现层；Source Item、Evidence 等属于 Result 内部内容的展开。它们不与阶段、运行实例、结果和配置值混在同一层建模。

技术契约现已确定普通 Run、完整 Profile、准备回读及直接来源对应的具体承诺；该工作以本页模型为依据，当前调用遵循 [docs/spec/contract](../spec/contract/index.md)。

[实施路线](../../openspec/changes/simplify-precheck-run-composition/README.md)保留后续合约与工程讨论，不是本模型的第二份定义。
