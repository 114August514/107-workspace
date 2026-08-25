import { Banner, Text, UnderlineNav } from '@primer/react'
import { useState } from 'react'

import type { LogChunk, LogStream } from '../../api/types'
import styles from './run.module.css'

function defaultStream(chunks: LogChunk[], failed: boolean): LogStream | undefined {
  const hasContent = (stream: LogStream) =>
    chunks.find((chunk) => chunk.stream === stream && chunk.content.trim())

  if (failed && hasContent('stderr')) return 'stderr'
  return chunks.find((chunk) => chunk.content.trim())?.stream ?? chunks[0]?.stream
}

interface Props {
  chunks: LogChunk[]
  /** Run 失败时优先打开 stderr，直接把诊断入口放在用户眼前。 */
  failed?: boolean
}

/** 标准输出与标准错误；后端返回前已完成已知 Secret 明文抹除。 */
export function RunLogPanel({ chunks, failed = false }: Props) {
  const [stream, setStream] = useState<LogStream | undefined>(() => defaultStream(chunks, failed))
  const active = chunks.find((chunk) => chunk.stream === stream) ?? chunks[0]

  if (!active) {
    return <Text className={styles.muted}>这个 Run 还没有日志输出。</Text>
  }

  return (
    <div className={styles.logPanel}>
      <UnderlineNav aria-label="Run 日志输出">
        {chunks.map((chunk) => (
          <UnderlineNav.Item
            key={chunk.stream}
            aria-current={active.stream === chunk.stream ? 'page' : undefined}
            onSelect={() => setStream(chunk.stream)}
          >
            {chunk.stream === 'stdout' ? '标准输出' : '标准错误'}
          </UnderlineNav.Item>
        ))}
      </UnderlineNav>
      {active.truncated ? (
        <Banner variant="warning">
          <Banner.Title>日志内容不完整</Banner.Title>
          <Banner.Description>日志过长，这里只显示尾部内容。</Banner.Description>
        </Banner>
      ) : null}
      {active.content.trim() ? (
        <pre className={styles.logConsole} tabIndex={0} aria-label={`${active.stream} 日志`}>
          {active.content}
        </pre>
      ) : (
        <div className={styles.emptyInline}>这一路输出目前是空的。</div>
      )}
      <Text as="p" size="small" className={styles.logNote}>
        日志中的 Secret 明文会由服务端替换成 ***。
      </Text>
    </div>
  )
}
