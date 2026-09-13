---
id: "index-model"
title: "基础概念模型"
type: index
status: active
created: 2026-09-13
updated: 2026-09-13
timezone: "Asia/Shanghai"
parent: "index-docs"
depends-on: []
superseded-by: ""
---

# 基础概念模型

本目录是基础建模的稳定阅读入口。新设计和合约工作先读取适用模型，理解有哪些概念、它们是什么种类、相互关系以及实例变化规则。

每个主题保留一份当前权威正文，在原路径持续维护；文件日期记录建立时间，不随实现发布重新命名或复制。模型的实质变更需要明确审阅。AGENTS.md、设计文档和合约引用这里，避免重复定义。

| 模型 | 标题 | 状态 | 建立日期 | 范围 |
| --- | --- | --- | --- | --- |
| [PreCheck](model-260913-1408-precheck-basics.md) | PreCheck 基础概念模型：阶段、Run、Result 与 Profile | active | 2026-09-13 | 已确认概念种类、关系和实例变化；改变要求创建新的普通 Run，Profile 为配置值。 |

模型保持业务无关。计算、缓存、调度和存储的实现选择归入[设计文档](../design/index.md)；请求、返回、效果和失败承诺归入[当前对外合约](../spec/contract/index.md)。模型确认、合约定稿和实现验收分别记录，不能相互替代。
