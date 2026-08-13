import { Flash, Spinner, Text } from '@primer/react'
import type { ReactNode } from 'react'

import { ApiError } from '../../api/client'

interface Props {
  loading: boolean
  error: Error | undefined
  empty?: boolean
  emptyText?: string
  children: ReactNode
}

function Padded({ children }: { children: ReactNode }) {
  return <div style={{ padding: 16 }}>{children}</div>
}

/** 统一处理加载中、出错和空状态（Primer 版）。 */
export function PrimerAsyncSection({ loading, error, empty, emptyText, children }: Props) {
  if (loading) {
    return (
      <Padded>
        <Spinner size="small" srText="加载中" />
      </Padded>
    )
  }

  if (error) {
    const problems = error instanceof ApiError ? error.problems : []
    const requestId = error instanceof ApiError ? error.requestId : ''
    return (
      <Padded>
        <Flash variant="danger">
          {error.message}
          {problems.length > 0 && (
            <ul style={{ margin: 0, paddingInlineStart: 20, marginTop: 8 }}>
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          )}
          {requestId && (
            <div style={{ marginTop: 8 }}>
              <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
                请求标识 {requestId}
              </Text>
            </div>
          )}
        </Flash>
      </Padded>
    )
  }

  if (empty) {
    return (
      <Padded>
        <Text
          size="small"
          style={{
            color: 'var(--fgColor-muted)',
            display: 'block',
            textAlign: 'center',
            padding: '32px 0',
          }}
        >
          {emptyText ?? '暂无数据'}
        </Text>
      </Padded>
    )
  }

  return <>{children}</>
}
