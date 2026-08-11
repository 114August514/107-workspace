# 延后设计事项

用于记录已经识别、但尚未进入正式领域模型或实现范围的详细设计事项。
这里不是第二份 Roadmap：产品方向与顺序以 [`design.md`](design.md) 第六章为准；某项进入正式设计范围后，应把细节迁移至对应设计并关闭本项。

---

## Domain / Product

### TODO-DOM-001 — 统一可共享资产与社区发现模型

Template Gallery 是活动的产品演进方向，按 `design.md` §2.4 和 §6.3 在不可变 Template Revision、Shared Resource、Visibility 与治理语义稳定后推进。当前延后的是把多类资产统一为 Gallery / Explore 或 `Shareable Asset` 的抽象，而不是模板发现能力本身。

只有证据表明 Environment、Shared Resource、Template 与 Profile 确实需要共同语义时，才重新评估：

- 统一 Visibility 与 Gallery Listing；
- Asset Transfer；
- Community / Featured 展示语义；
- 多类资产是否需要统一 `Shareable Asset` 抽象。

重新评估时机：Template Gallery 的具体治理需求无法由 Template 与 Workspace 现有语义表达时。

---

### TODO-DOM-002 — Official Asset 与官方资产库

当前不将 Official Asset、Official Library 或社区晋升流程纳入核心领域模型。

未来需要基于真实运营需求考虑：

- Community、Featured、Official 的语义；
- 平台如何从高质量社区资产形成 Official Asset；
- Official Template / Profile Library；
- Promote 是否创建官方副本；
- Creator Attribution 与 Source Provenance；
- 官方资产由运营方维护的 Collaborative Workspace 持有，还是需要其他 Ownership 模型。

当前倾向仍是优先复用 Collaborative Workspace，而不是预先新增 Workspace 类型。

---

### TODO-DOM-003 — Course Profile 专用领域对象

Course Profile 是 `design.md` §2.11 和 §6.3 的活动产品演进方向；当前延后的是 Course 专用领域对象的详细模型与契约，不是把课程场景移出 Roadmap。

它只能在 Fork、Role、Project Version 与 Run Snapshot 语义稳定后进入设计，并必须编排而非绕过 Workspace、Project、Run、权限与版本规则。届时根据实际需要细化：

- Assignment；
- Submission；
- Instructor / TA / Student；
- Trusted Evaluation；
- 课程场景工作流与生命周期。
