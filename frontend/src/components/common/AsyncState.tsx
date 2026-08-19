import { FileDirectoryIcon } from '@primer/octicons-react'
import { Banner, Spinner, Text } from '@primer/react'
import { Blankslate } from '@primer/react/experimental'
import type { ReactNode } from 'react'

interface Props {
  loading: boolean
  /** 已经归一化的错误展示数据；组件不依赖 API client，由调用方拆解错误对象。 */
  error?: { message: string; problems?: string[]; requestId?: string }
  /** 可恢复错误的重试回调；提供时错误态会渲染「重试」主操作。 */
  onRetry?: () => void
  empty?: boolean
  /** 空态标题；说明缺什么。 */
  emptyText?: string
  /** 空态说明；下一步或后果。 */
  emptyDescription?: string
  /**
   * 空态主操作的内容（按钮文字或图标）。Blankslate.PrimaryAction 自己会渲染成
   * Primer Button，所以这里传的是按钮内容，不要再套一层 <Button>，否则会
   * button 套 button 产出非法 HTML。
   */
  emptyAction?: ReactNode
  /** 空态主操作的点击回调，透传给 PrimaryAction 渲染出的 Button。 */
  onEmptyAction?: () => void
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
export function AsyncState({
  loading,
  error,
  onRetry,
  empty,
  emptyText,
  emptyDescription,
  emptyAction,
  onEmptyAction,
  children,
}: Props) {
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
        <Banner variant="critical">
          <Banner.Title>{error.message}</Banner.Title>
          <Banner.Description>
            {/* 单条是“下一步”说明，直接成一行；多条才是需要逐条修正的问题列表 */}
            {problems.length === 1 ? (
              <div>{problems[0]}</div>
            ) : problems.length > 1 ? (
              <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                {problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            ) : null}
            {error.requestId && (
              <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
                请求标识 {error.requestId}
              </Text>
            )}
          </Banner.Description>
          {onRetry ? <Banner.PrimaryAction onClick={onRetry}>重试</Banner.PrimaryAction> : null}
        </Banner>
      </Padded>
    )
  }

  if (empty) {
    return (
      <Padded>
        <Blankslate narrow>
          <Blankslate.Visual>
            <FileDirectoryIcon size={24} />
          </Blankslate.Visual>
          <Blankslate.Heading>{emptyText ?? '暂无数据'}</Blankslate.Heading>
          {emptyDescription ? (
            <Blankslate.Description>{emptyDescription}</Blankslate.Description>
          ) : null}
          {emptyAction ? (
            <Blankslate.PrimaryAction onClick={onEmptyAction}>
              {emptyAction}
            </Blankslate.PrimaryAction>
          ) : null}
        </Blankslate>
      </Padded>
    )
  }

  return <>{children}</>
}
