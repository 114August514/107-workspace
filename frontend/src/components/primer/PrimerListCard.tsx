import { Heading } from '@primer/react'
import type { ReactNode } from 'react'

import styles from './PrimerListCard.module.css'

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
 * 长期视觉规则在 PrimerListCard.module.css，取色走 Primer token。
 */
export function PrimerListCard({ title, extra, padded = false, children }: Props) {
  return (
    <div className={styles.card}>
      {(title || extra) && (
        <div className={styles.header}>
          {title && (
            <Heading as="h3" variant="small">
              {title}
            </Heading>
          )}
          {extra}
        </div>
      )}
      <div className={padded ? styles.body : undefined}>{children}</div>
    </div>
  )
}
