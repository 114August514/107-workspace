import { RelativeTime, Text } from '@primer/react'

interface MonoProps {
  children: string
  /** 只显示前若干个字符 */
  truncate?: number
}

/**
 * 标识符等宽显示（Primer 版）。
 *
 * 等宽字体下 run_0980 和 run_098O 一眼能看出不一样。
 * 字体走 Primer Primitives 的 monospace stack，不引入 antd theme。
 */
export function PrimerMono({ children, truncate }: MonoProps) {
  const shown =
    truncate && children.length > truncate ? `${children.slice(0, truncate)}…` : children
  return (
    <Text as="code" size="small" style={{ fontFamily: 'var(--fontStack-monospace)' }}>
      {shown}
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
