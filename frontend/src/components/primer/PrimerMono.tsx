import { RelativeTime, Text } from '@primer/react'

import { fontFamilyCode } from '../../theme'

interface MonoProps {
  children: string
  /** 只显示前若干个字符 */
  truncate?: number
}

/**
 * 标识符等宽显示（Primer 版）。
 *
 * 等宽字体下 run_0980 和 run_098O 一眼能看出不一样。
 */
export function PrimerMono({ children, truncate }: MonoProps) {
  const shown = truncate && children.length > truncate ? children.slice(0, truncate) : children
  return (
    <Text as="code" size="small" style={{ fontFamily: fontFamilyCode, fontSize: 12 }}>
      {shown === children ? children : `${children.slice(0, truncate)}…`}
    </Text>
  )
}

/**
 * 相对时间，title 属性显示绝对时间（Primer 版）。
 */
export function PrimerRelativeTime({ value }: { value: string | null | undefined }) {
  if (!value)
    return (
      <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
        —
      </Text>
    )
  return <RelativeTime datetime={value} />
}
