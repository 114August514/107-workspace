import { Heading } from '@primer/react'
import type { ReactNode } from 'react'

interface Props {
  title?: ReactNode
  extra?: ReactNode
  /** body 是否需要内边距（非表格内容传 true） */
  padded?: boolean
  children: ReactNode
}

/**
 * 装列表用的盒子（Primer 版）。
 *
 * body 内边距默认为 0，表头直接贴着卡片标题栏，共用底色读起来是一整块。
 */
export function PrimerListCard({ title, extra, padded = false, children }: Props) {
  return (
    <div
      style={{
        border: '1px solid var(--borderColor-default, #d1d9e0)',
        borderRadius: 6,
        overflow: 'hidden',
        backgroundColor: 'var(--bgColor-default, #fff)',
      }}
    >
      {(title || extra) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 16px',
            backgroundColor: 'var(--bgColor-muted, #f6f8fa)',
            borderBottom: '1px solid var(--borderColor-default, #d1d9e0)',
          }}
        >
          {title && (
            <Heading as="h3" variant="small">
              {title}
            </Heading>
          )}
          {extra}
        </div>
      )}
      <div style={padded ? { padding: 16 } : undefined}>{children}</div>
    </div>
  )
}
