import { Stack } from '@primer/react'
import type { ReactNode } from 'react'

interface Props {
  gap?: 'small' | 'middle' | 'large'
  children: ReactNode
}

/** 竖排 flex 布局，替代 antd Space direction="vertical"。 */
export function PrimerStack({ gap = 'middle', children }: Props) {
  const gapScale = gap === 'small' ? 'condensed' : gap === 'middle' ? 'normal' : 'spacious'
  return (
    <Stack direction="vertical" gap={gapScale} style={{ width: '100%' }}>
      {children}
    </Stack>
  )
}
