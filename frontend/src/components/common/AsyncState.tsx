import { Flash, Spinner, Text } from '@primer/react'
import type { ReactNode } from 'react'

interface Props {
  loading: boolean
  /** 已经归一化的错误展示数据；组件不依赖 API client，由调用方拆解错误对象。 */
  error?: { message: string; problems?: string[]; requestId?: string }
  empty?: boolean
  emptyText?: string
  children: ReactNode
}

/**
 * 加载中、出错、空状态都不是列表，所以要自带内边距——
 * 装它们的容器内边距通常是 0（那是给表格用的），
 * 不垫一下的话骨架屏和空状态会直接贴着卡片边框。
 */
function Padded({ children }: { children: ReactNode }) {
  return <div style={{ padding: 16 }}>{children}</div>
}

/**
 * 网络数据区的统一异步状态（Primer 版）：加载、失败、空。
 *
 * 提交前检查这类错误会带回多条问题，这里逐条展示，
 * 而不是只显示第一条让用户来回试；请求标识一起给出，
 * 服务端照着就能查到这次请求的日志。
 *
 * 与旧 Ant Design 的 components/common/AsyncSection 并存：
 * 未迁移页面继续用旧的，已迁移 Primer surface 用这个。
 */
export function AsyncState({ loading, error, empty, emptyText, children }: Props) {
  if (loading) {
    return (
      <Padded>
        <Spinner size="small" srText="加载中" />
      </Padded>
    )
  }

  if (error) {
    const problems = error.problems ?? []
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
          {error.requestId && (
            <div style={{ marginTop: 8 }}>
              <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
                请求标识 {error.requestId}
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
