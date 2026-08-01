import { Breadcrumb, Space, Typography } from 'antd'
import type { ReactNode } from 'react'

interface Props {
  /** 面包屑。只有一级的页面可以不传。 */
  breadcrumb?: { title: ReactNode }[]
  title: ReactNode
  /** 跟在标题右边的标签，比如空间类型、角色、Run 状态。 */
  tags?: ReactNode
  /** 标题下面一行说明。 */
  description?: ReactNode
  /** 右上角的操作按钮。 */
  actions?: ReactNode
}

/**
 * 页面顶部。
 *
 * 之前每个页面各写各的：`<div>` 包 `Typography.Title level={3}` 再包一层
 * `Space`，四个页面四种写法，标题字号和间距都对不齐。
 *
 * 字号刻意压到 20px（antd 的 level=4）。level=3 是 24px，在一个以列表
 * 为主的界面里，页面标题不需要比内容大那么多——**要扫的是下面的列表，
 * 不是标题**。
 */
export function PageHeader({ breadcrumb, title, tags, description, actions }: Props) {
  return (
    <div>
      {breadcrumb && breadcrumb.length > 0 && (
        <Breadcrumb items={breadcrumb} style={{ marginBottom: 8 }} />
      )}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <Space align="center" wrap size={8}>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {title}
            </Typography.Title>
            {tags}
          </Space>
          {description && (
            <div style={{ marginTop: 2 }}>
              <Typography.Text type="secondary">{description}</Typography.Text>
            </div>
          )}
        </div>
        {actions && <Space>{actions}</Space>}
      </div>
    </div>
  )
}
