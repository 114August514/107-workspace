import '@primer/primitives/dist/css/base/size/size.css'
import '@primer/primitives/dist/css/base/typography/typography.css'
import '@primer/primitives/dist/css/functional/size/border.css'
import '@primer/primitives/dist/css/functional/size/radius.css'
import '@primer/primitives/dist/css/functional/size/size.css'
import '@primer/primitives/dist/css/functional/typography/typography.css'
import '@primer/primitives/dist/css/functional/themes/light.css'

import { BaseStyles, ThemeProvider } from '@primer/react'
import type { ReactNode } from 'react'

/**
 * 107 Workspace 唯一的 Primer runtime 入口。
 *
 * ThemeProvider、BaseStyles 和 primitives token CSS 只允许在这里接入一次。
 * /design-system 与后续已迁移的 Primer surface 都消费这个入口；
 * 不要为某个页面再单独包一层 ThemeProvider 或重复 import token CSS，
 * 否则同一页面会出现两套 token 来源，谁也改不动。
 *
 * primitives token 通过 [data-color-mode] 属性作用域生效，
 * 组件样式走 hashed class，因此迁移期间包住未迁移的 Ant Design
 * 页面不会覆盖其主题；BaseStyles 的元素级排版规则（body 字号、链接颜色）
 * 对旧页面的影响由浏览器回归验证兜底。
 *
 * App 根（App.tsx）已接入唯一一层 PrimerRoot；任何 surface 都不要再自行包一层。
 */
export function PrimerRoot({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider colorMode="day">
      <BaseStyles>{children}</BaseStyles>
    </ThemeProvider>
  )
}
