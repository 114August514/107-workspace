import { Space } from 'antd'
import type { ReactNode } from 'react'

interface Props {
  gap?: 'small' | 'middle' | 'large'
  children: ReactNode
}

/**
 * 竖排并撑满宽度。
 *
 * 在此之前 `<Space direction="vertical" size="..." style={{ width: '100%' }}>`
 * 这一串在十几个文件里逐字重复。它没写错，但每多抄一遍就多一个漏掉
 * `width: '100%'` 的机会——漏掉之后 Space 会缩成内容宽度，表格跟着塌一半，
 * 而这种塌法在有数据的时候不明显，空列表时才露出来。
 */
export function Stack({ gap = 'middle', children }: Props) {
  return (
    <Space direction="vertical" size={gap} style={{ width: '100%' }}>
      {children}
    </Space>
  )
}
