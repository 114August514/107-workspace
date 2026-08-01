/**
 * 全站视觉令牌。
 *
 * **界面样式一律在这里改，不要在组件里堆 style 或者写 CSS 文件。**
 * antd 的组件全部按这套 token 渲染，改一个值全站跟着变；
 * 散在组件里的行内样式改不动，也没人知道有几处。
 *
 * 取向借鉴 GitHub 这类面向开发者的工具，因为它要解决的是同一个问题：
 * 屏幕上要放很多条目（文件、版本、运行记录），用户是来**扫**的，不是来欣赏的。
 * 具体是三条：
 *
 *     用边框分区，不用阴影      阴影让每个盒子都在「浮起来」，一屏放五个就很吵
 *     密度优先                  行高和留白压紧，一屏能多看几行就少翻一页
 *     颜色只用来表达状态        通篇近乎黑白，绿色红色一出现就是有事发生
 */

import type { ThemeConfig } from 'antd'

/**
 * 中性色阶。命名按用途而不是按色值，改的时候不用猜。
 *
 * **组件里不要再写死颜色**，一律从这里取。有一条测试守着这件事
 * （`theme.test.ts`）——散在各处的色值是没法统一改的，
 * 换配色时总会漏掉几个，然后界面就花了。
 */
export const colors = {
  canvas: '#ffffff',
  /** 表头、悬停行、代码块的背景。比白色重一点点，够区分又不抢视线。 */
  subtle: '#f6f8fa',
  border: '#d1d9e0',
  text: '#1f2328',
  textMuted: '#59636e',
  /** 顶栏这类深色区域，以及它上面的文字。 */
  headerBg: '#24292f',
  onDark: '#ffffff',
  onDarkMuted: 'rgba(255, 255, 255, 0.75)',
  /**
   * 顶栏上的未读徽标。
   *
   * 不能直接用 colorError（#cf222e）——那是给白底准备的，
   * 放到深色顶栏上只有 2.74:1，达不到 UI 元件要求的 3:1，看着就是一个暗红点。
   * 换成亮红加深色数字，两项都过：徽标对顶栏 5.81:1，数字对徽标 5.81:1。
   */
  badgeOnDark: '#ff7b72',
  badgeOnDarkText: '#24292f',
  /** 日志区。终端配色是刻意的：看日志时的心智就是在看终端。 */
  terminalBg: '#1e1e1e',
  terminalText: '#e6e6e6',
} as const

const canvas = colors.canvas
const subtle = colors.subtle
const border = colors.border
const text = colors.text
const textMuted = colors.textMuted

/** 强调色。链接和选中态用蓝，主按钮用绿——见下面 Button 的注释。 */
const accent = '#0969da'
const success = '#1a7f37'
const danger = '#cf222e'
const warning = '#9a6700'

/** 正文字体。中文优先落到系统里已有的字体，不额外加载 web font。 */
const fontFamily = [
  '-apple-system',
  'BlinkMacSystemFont',
  '"Segoe UI"',
  '"PingFang SC"',
  '"Hiragino Sans GB"',
  '"Microsoft YaHei"',
  '"Noto Sans CJK SC"',
  'Helvetica',
  'Arial',
  'sans-serif',
].join(', ')

/** 等宽字体。用于一切「标识符」：ID、路径、命令、日志。 */
export const fontFamilyCode = [
  'ui-monospace',
  'SFMono-Regular',
  '"SF Mono"',
  'Menlo',
  'Consolas',
  '"Liberation Mono"',
  'monospace',
].join(', ')

export const theme: ThemeConfig = {
  token: {
    colorPrimary: accent,
    colorInfo: accent,
    colorSuccess: success,
    colorError: danger,
    colorWarning: warning,

    colorText: text,
    colorTextSecondary: textMuted,
    colorTextDescription: textMuted,

    // colorBorderSecondary 是 Card、Table 这些容器实际用的边框色。
    // antd 默认给的是几乎看不见的浅灰，于是盒子只能靠阴影才显出边界。
    // 这里两个都调成看得见的实线，阴影就可以彻底去掉。
    colorBorder: border,
    colorBorderSecondary: border,

    colorBgLayout: canvas,
    colorBgContainer: canvas,

    borderRadius: 6,
    borderRadiusLG: 6,
    borderRadiusSM: 4,

    fontFamily,
    fontFamilyCode,
    fontSize: 14,

    controlHeight: 32,

    // 只有真正浮在页面之上的东西（下拉、气泡、对话框）才有阴影。
    // 页面里的卡片和表格一律用边框，boxShadowTertiary 是它们用的那个。
    boxShadowTertiary: 'none',
  },

  components: {
    Layout: {
      headerBg: colors.headerBg,
      headerHeight: 56,
      headerPadding: '0 24px',
      bodyBg: canvas,
      footerBg: canvas,
      footerPadding: '24px 32px',
    },

    Card: {
      // 表头条：卡片标题和表格表头用同一个底色，读起来是一整块
      headerBg: subtle,
      headerHeight: 44,
      headerHeightSM: 40,
      headerFontSize: 14,
      headerFontSizeSM: 14,
      // 卡片自己的内边距收紧；装表格时还会在 ListCard 里把它清零
      bodyPadding: 16,
      bodyPaddingSM: 12,
    },

    Table: {
      // 表头**不加底色**。装表格的 ListCard 自己有一条灰色标题栏，
      // 表头再来一条就是两条灰带叠在一起，中间那条没有任何信息量。
      // 列名靠字重和下边框就够分辨了。
      headerBg: 'transparent',
      headerColor: textMuted,
      headerSplitColor: 'transparent',
      borderColor: border,
      rowHoverBg: subtle,
      // 行高压到接近 GitHub 的列表：一屏能多看四五行
      cellPaddingBlock: 10,
      cellPaddingInline: 16,
      cellPaddingBlockSM: 8,
      cellPaddingInlineSM: 12,
      headerBorderRadius: 0,
    },

    Button: {
      // 主按钮用绿色，链接和选中态用蓝色。
      // 这样「可点的东西」和「会改变数据的那个按钮」在视觉上是两件事——
      // 一屏上蓝色可能有十几处，绿色永远只有一个。
      colorPrimary: success,
      colorPrimaryHover: '#1c8139',
      colorPrimaryActive: '#187733',
      primaryShadow: 'none',
      defaultShadow: 'none',
      dangerShadow: 'none',
      fontWeight: 500,
      paddingInline: 12,
    },

    Tabs: {
      horizontalItemPadding: '8px 2px',
      horizontalItemGutter: 24,
      horizontalMargin: '0 0 16px 0',
      titleFontSize: 14,
    },

    Tag: {
      defaultBg: subtle,
      defaultColor: textMuted,
      borderRadiusSM: 12,
    },

    Descriptions: {
      labelBg: subtle,
      titleMarginBottom: 12,
      itemPaddingBottom: 8,
    },

    Breadcrumb: {
      fontSize: 14,
      separatorMargin: 6,
    },

    Empty: {
      // 空状态不需要占半屏
      controlHeightLG: 32,
    },

    Timeline: {
      dotBg: canvas,
    },

    Alert: {
      defaultPadding: '8px 12px',
      withDescriptionPadding: '12px 16px',
    },
  },
}
