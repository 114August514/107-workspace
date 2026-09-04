# USTC VIS 与 107 Workspace 品牌输入

本页只记录 Issue #64 使用的外部来源、已核实事实和吸收边界。它不是对学校
VIS 的替代，也不把 107 Workspace 的网页配色声明为学校规范。

## 官方来源

- 中国科学技术大学党建与思政网：[中国科学技术大学识别手册](https://djyszw.ustc.edu.cn/info/1070/6829.htm)
- 上述页面发布的官方手册归档：[A—基础部分 JPG](https://djyszw.ustc.edu.cn/__local/4/0B/68/4B30730049294F1DA5BF8DCA920_5BC2B25F_1F4C45C.rar?e=.rar)
- 中国科学技术大学研究生会：[会议纪要中对“科大蓝（C100 M80 Y0 K0）”的独立使用记录](https://gradunion.ustc.edu.cn/2024/0321/c5681a633466/page.htm)
- 中国科学技术大学苏州高等研究院：[校徽说明与官方素材下载入口](https://sz.ustc.edu.cn/wdxz_show/13.html)

核验日期：2026-08-23。只接受 `ustc.edu.cn` 及其官方子域发布的材料；搜索截图、
第三方素材站和网页肉眼取色不作为数值来源。

## 已核实事实

官方《视觉形象识别系统管理手册（试行）》说明，VIS 以校徽、校名、标准色为核心，
由基础系统与应用系统组成。与本项目直接相关的手册页为：

- A01-02 / A01-03：校徽含义、网格与最小尺寸；校徽使用 16 单位网格，印刷最小边长不得小于 10 mm；
- A01-05 / A01-06：阴阳图版与单色、反白等使用形式；
- A01-07：色彩系统；
- A03-01 至 A03-03：非标准色、改变基本形态、扭曲和干扰背景等禁止示例。

学校标准色的权威数值是：

```text
C100 M80 Y0 K0
```

这是印刷 CMYK 输入。已核实材料没有给出 RGB 或 HEX，因此本项目不得把任何 HEX
称为“USTC 官方蓝”。学校校徽、校名和规定组合属于 USTC affiliation，不得拆解、
重绘、任意改色或拼接成 107 产品标识；也不直接用作 16 px favicon。

手册同时列出红、浅蓝、黑、灰、白、金、银、褐等辅助印刷色。它们不自动成为产品
success、warning、danger 或其他界面语义色；这些职责继续由 Primer semantic tokens
承担。

## 当前 107 Workspace 单色品牌

当前产品身份采用黑白灰体系。active Brand Mark 使用
`frontend/src/assets/brand/107_pig_final.svg`，由 3 条 path 构成，path 使用静态
`#000000` 填充；透明负空间在当前浅色画布上呈现为白色。灰色不直接绘入 SVG，由 Primer
neutral 与 state tokens 负责。

页面 `BrandMark.tsx` 与 `frontend/public/favicon.svg` 复用同一份 final 几何和黑色静态填充；为让图形在 16 / 24 / 32 px
容器内占满接近 GitHub 常见产品 Mark 的可视面积，使用紧凑 `viewBox="20 20 101 101"`，不改变宽高比。
不再使用旧 Mark 的 optical padding，也不保留运行时 Mark 切换或 fallback。原始 `107pig.svg` 保留在
`docs/archive/brand/107pig.svg`，仅用于来源追溯，不属于当前 active brand。

当前界面颜色职责直接复用 Primer neutral tokens：

```text
primary        var(--fgColor-default)
primary hover  var(--fgColor-muted)
on primary     var(--bgColor-default)
subtle         var(--bgColor-muted)
foreground     var(--fgColor-default)
border         var(--borderColor-default)
```

## 后续调研候选：蓝白 web adaptation

蓝白配色暂不进入当前 UI，仅作为后续单独调查的候选记录：

```text
primary        #0455B6
primary hover  #00458F
on primary     #FFFFFF
subtle         #DDEBFF
foreground     #003B78
border         #4F83BE
```

这些 sRGB 值是 107 Workspace 的 web adaptation，不是官方 USTC RGB/HEX，也不是从官方
手册 JPG 或学校网页截图采样得到。选择方法是：仅把官方 `C100 M80 Y0 K0` 作为深蓝输入，
再以 WCAG 对比度和明确界面职责评估候选值。

当前候选测量结果（不代表 active UI）：

| 组合                                            | 对比度 |
| :---------------------------------------------- | -----: |
| `#0455B6` / `#FFFFFF`                           | 7.05:1 |
| `#00458F` / `#FFFFFF`                           | 9.34:1 |
| `#003B78` / `#DDEBFF`                           | 9.17:1 |
| `#0455B6` / Primer light muted canvas `#F6F8FA` | 6.62:1 |
| `#4F83BE` / `#FFFFFF`                           | 3.95:1 |
| `#4F83BE` / `#DDEBFF`                           | 3.27:1 |

蓝白候选保留用于后续视觉与可访问性调查；在明确调查结论前，禁止将其称为当前品牌色。

## 当前吸收边界

- Primer 继续负责 neutral canvas、正文、边框、间距、排版、控件交互与 semantic status；
- 107 brand layer 只负责产品 Mark、wordmark 和少量 link、selected、focus、primary affordance；
- 最终 Mark 已接入真实 AppShell（TopBar 32 px）并生成 favicon；
- 当前人工确认覆盖 final 几何与黑白 active 方案；蓝白配色仍是后续调查候选，尚未定稿。
