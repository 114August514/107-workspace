import { Alert, Empty, Skeleton, Typography } from 'antd'
import type { ReactNode } from 'react'

import { ApiError } from '../../api/client'

interface Props {
  loading: boolean
  error: Error | undefined
  empty?: boolean
  emptyText?: string
  children: ReactNode
}

/**
 * 统一处理加载中、出错和空状态。
 *
 * 提交前检查这类错误会带回多条问题，这里逐条展示，
 * 而不是只显示第一条让用户来回试。
 */
/**
 * 加载中、出错、空状态都不是列表，所以要自带内边距——
 * 装它们的 ListCard 内边距是 0（那是给表格用的），
 * 不垫一下的话骨架屏和空状态会直接贴着卡片边框。
 */
function Padded({ children }: { children: ReactNode }) {
  return <div style={{ padding: 16 }}>{children}</div>
}

export function AsyncSection({ loading, error, empty, emptyText, children }: Props) {
  if (loading) {
    return (
      <Padded>
        <Skeleton active paragraph={{ rows: 3 }} />
      </Padded>
    )
  }

  if (error) {
    const problems = error instanceof ApiError ? error.problems : []
    const requestId = error instanceof ApiError ? error.requestId : ''
    return (
      <Padded>
        <Alert
          type="error"
          showIcon
          message={error.message}
          description={
            problems.length > 0 || requestId ? (
              <>
                {problems.length > 0 && (
                  <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                    {problems.map((problem) => (
                      <li key={problem}>{problem}</li>
                    ))}
                  </ul>
                )}
                {requestId && (
                  // 报问题时把它一起给出来，服务端照着就能查到这次请求的日志
                  <Typography.Text type="secondary" copyable style={{ fontSize: 12 }}>
                    {`请求标识 ${requestId}`}
                  </Typography.Text>
                )}
              </>
            ) : undefined
          }
        />
      </Padded>
    )
  }

  if (empty) {
    return (
      <Padded>
        <Empty description={emptyText ?? '暂无数据'} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Padded>
    )
  }

  return <>{children}</>
}
