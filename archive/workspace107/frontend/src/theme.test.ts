import { describe, expect, it } from 'vitest'

import { colors, theme } from './theme'

/**
 * 用 vite 的 glob 读源码，而不是 node:fs——这样不必为一条测试引入
 * `@types/node`，测试环境也和应用代码保持一致。
 */
const sources = import.meta.glob('./**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

/** 视觉令牌只能有一处定义。 */
const TOKEN_FILE = './theme.ts'

function isChecked(path: string): boolean {
  if (path === TOKEN_FILE) return false
  if (path.includes('.test.')) return false
  // 生成物不归我们管
  if (path.endsWith('schema.d.ts')) return false
  return true
}

describe('视觉令牌', () => {
  it('颜色只在 theme.ts 里定义', () => {
    // 散在各处的色值没法统一改。换配色时总会漏掉几个，然后界面就花了——
    // 而且漏掉的那几个往往在不常打开的页面上，很久都没人发现。
    const offenders = Object.entries(sources)
      .filter(([path]) => isChecked(path))
      .map(([path, source]) => {
        const found = source.match(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)/g)
        return found ? `${path}: ${found.join(', ')}` : null
      })
      .filter(Boolean)

    expect(offenders, '这些文件里写死了颜色，请改成从 theme.ts 的 colors 取').toEqual([])
  })

  it('没有 CSS 文件', () => {
    // 样式全部走 antd 的 token。开一个 .css 就等于开了一条绕过令牌的路，
    // 之后的覆盖会越堆越多，而且和 token 互相打架。
    const css = import.meta.glob('./**/*.css', { eager: true })
    expect(Object.keys(css)).toEqual([])
  })

  it('主按钮和链接不是同一个颜色', () => {
    // 一屏上蓝色链接可能有十几处，而「会改变数据的那个按钮」只有一个。
    // 两者同色的话，主按钮就淹没在链接里了。
    expect(theme.components?.Button?.colorPrimary).not.toBe(theme.token?.colorPrimary)
  })

  it('容器不用阴影', () => {
    // 卡片、表格靠边框划分区域。阴影让每个盒子都在「浮起来」，一屏放五个就很吵。
    expect(theme.token?.boxShadowTertiary).toBe('none')
    expect(theme.token?.colorBorderSecondary).toBe(colors.border)
  })
})
