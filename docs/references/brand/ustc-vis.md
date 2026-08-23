# USTC VIS 与 107 Workspace 品牌输入

本页只记录 Issue #64 使用的外部来源、已核实事实和吸收边界。它不是对学校
VIS 的替代，也不把 107 Workspace 的临时网页配色声明为学校规范。

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

## Issue #64 人工视觉门的临时网页适配

候选 Reference 使用以下临时 sRGB 值：

```text
primary        #0057B8
primary hover  #00458F
on primary     #FFFFFF
subtle         #DDEBFF
foreground     #003B78
border         #4F83BE
```

这些值是 **107 Workspace provisional web adaptation**，不是官方 USTC RGB/HEX，也不是
从官方手册 JPG 或学校网页截图采样得到。选择方法是：

1. 仅把官方 `C100 M80 Y0 K0` 作为“深蓝、以蓝为主”的品牌输入，不假装设备相关 CMYK
   可以无配置文件地唯一换算为 sRGB；
2. 在 sRGB 中选择克制的产品蓝 `#0057B8`，再分别为 hover、浅底前景、浅底和边界选择
   有明确界面职责的值；
3. 使用 WCAG 2.x 相对亮度公式检查真实组合，并把可访问性优先于与印刷色样的肉眼接近；
4. 人工视觉门选定 Mark 和品牌强度后，删除未采用候选；最终值若调整，在这里记录新的
   选择依据与证据。

当前计算结果（对比度，前景 / 背景）：

| 组合                                            | 对比度 |
| :---------------------------------------------- | -----: |
| `#0057B8` / `#FFFFFF`                           | 6.87:1 |
| `#00458F` / `#FFFFFF`                           | 9.34:1 |
| `#003B78` / `#DDEBFF`                           | 9.17:1 |
| `#0057B8` / Primer light muted canvas `#F6F8FA` | 6.46:1 |
| `#4F83BE` / `#FFFFFF`                           | 3.95:1 |
| `#4F83BE` / `#DDEBFF`                           | 3.27:1 |

因此 primary/on-primary 可承载普通文字，foreground/subtle 可承载 selected text，
primary 可作为浅色画布上的 focus outline，border 可作为相邻白色或 subtle 背景的
非文字边界。正式采用前仍需在真实 Primer 组件、桌面和 375 px 浏览器中复核。

## 当前吸收边界

- Primer 继续负责 neutral canvas、正文、边框、间距、排版、控件交互与 semantic status；
- 107 brand layer 只负责产品 Mark、wordmark 和少量 link、selected、focus、primary affordance；
- 当前 `/design-system` 同时呈现三个 Mark 候选，不提供切换器或运行时配置；
- 候选 2 在界面中明确标为 `候选 2 · 节点连接（image2）`，供人工检查；
- 未经人工选择，不修改真实 AppShell，也不生成 favicon，避免把候选误当成最终品牌。
