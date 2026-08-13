import { Breadcrumb, Heading, Link as PrimerLink, Stack, Text } from '@primer/react'
import type { ReactNode } from 'react'

interface Props {
  /** 面包屑 */
  breadcrumb?: { title: ReactNode }[]
  title: ReactNode
  /** 跟在标题右边的标签 */
  tags?: ReactNode
  /** 标题下面一行说明 */
  description?: ReactNode
  /** 右上角的操作按钮 */
  actions?: ReactNode
}

/**
 * 页面顶部（Primer 版）。
 *
 * 标题字号压到 20px，高度密集的数据界面里标题不需要比内容大太多。
 */
export function PrimerPageHeader({ breadcrumb, title, tags, description, actions }: Props) {
  return (
    <div>
      {breadcrumb && breadcrumb.length > 0 && (
        <Breadcrumb style={{ marginBottom: 8 }}>
          {breadcrumb.map((item, idx) => (
            <Breadcrumb.Item key={idx}>
              {typeof item.title === 'string' ? (
                <PrimerLink as="span" muted>
                  {item.title}
                </PrimerLink>
              ) : (
                item.title
              )}
            </Breadcrumb.Item>
          ))}
        </Breadcrumb>
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
          <Stack direction="horizontal" gap="condensed" style={{ alignItems: 'center' }}>
            <Heading as="h2" variant="medium">
              {title}
            </Heading>
            {tags}
          </Stack>
          {description && (
            <div style={{ marginTop: 4 }}>
              {typeof description === 'string' ? (
                <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
                  {description}
                </Text>
              ) : (
                description
              )}
            </div>
          )}
        </div>
        {actions && <div style={{ flexShrink: 0, display: 'flex', gap: 8 }}>{actions}</div>}
      </div>
    </div>
  )
}
