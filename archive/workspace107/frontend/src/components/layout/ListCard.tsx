import { Card } from 'antd'
import type { ReactNode } from 'react'

interface Props {
  title?: ReactNode
  extra?: ReactNode
  /** 列表以外的内容（说明文字、表单）需要内边距，传 true。 */
  padded?: boolean
  children: ReactNode
}

/**
 * 装列表用的盒子。
 *
 * 关键在于 **body 的内边距是 0**。之前的写法是 `<Card>` 里放 `<Table>`，
 * 于是同一条边界被画了两遍：卡片的边框和内边距，套着表格自己的边框和表头。
 * 中间那圈 16px 白边没有任何信息量，只是把每个列表都撑大一圈。
 *
 * 去掉之后，表头直接贴着卡片标题栏，两者共用一个底色，读起来是一整块——
 * 也就是 GitHub 上文件列表、提交列表那种盒子。
 */
export function ListCard({ title, extra, padded = false, children }: Props) {
  return (
    <Card
      title={title}
      extra={extra}
      size="small"
      styles={{ body: padded ? { padding: 16 } : { padding: 0 } }}
    >
      {children}
    </Card>
  )
}
