# 延后事项

用于记录已经识别、但当前明确延后的产品设计。这里的内容不构成当前产品规范；事项进入正式范围后，应迁移到对应设计中。

---

## Domain / Product

### TODO-DOM-001 — Gallery 与可共享资产模型

当前暂不设计 Gallery / Explore 以及统一的 `Shareable Asset` 抽象。

未来需要重新评估：

- Template、Profile、Environment、Shared Resource 的统一发布与发现模型；
- Visibility；
- Gallery Listing；
- Asset Transfer；
- Community / Featured 等展示语义；
- 是否需要统一的 Shareable Asset 抽象。

重新评估时机：正式设计 Gallery / Explore 时。

---

### TODO-DOM-002 — Official Asset 与官方资产库

当前暂不将 Official Asset 纳入核心领域模型。

未来需要考虑：

- Community、Featured、Official 的语义；
- 平台如何从高质量社区资产形成 Official Asset；
- Official Template / Profile Library；
- Promote 是否创建官方副本；
- Creator Attribution 与 Source Provenance；
- 官方资产由普通 Collaborative Workspace 持有，还是引入其他 Ownership 模型。

当前倾向：官方库优先建模为平台运营方维护的 Collaborative Workspace，而不是新增 Workspace 类型。

---

### TODO-DOM-003 — Course Profile

当前不设计 Course 专用领域对象。

未来以 Course Profile 验证 Profile 扩展机制，并根据实际需要考虑：

- Assignment；
- Submission；
- Instructor / TA / Student；
- Trusted Evaluation；
- 课程场景工作流。

Course Profile 不得绕过 Workspace、Project、Run、权限与版本规则。
