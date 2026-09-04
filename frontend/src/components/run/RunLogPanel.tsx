import { DownloadIcon } from '@primer/octicons-react'
import { Banner, Button, SegmentedControl, Text } from '@primer/react'
import { useEffect, useRef, useState } from 'react'

import { api } from '../../api/client'
import type { LogChunk, LogStream } from '../../api/types'
import { CodeViewer } from '../common/CodeViewer'
import styles from './run.module.css'

function defaultStream(chunks: LogChunk[], failed: boolean): LogStream | undefined {
  const hasContent = (stream: LogStream) =>
    chunks.find((chunk) => chunk.stream === stream && chunk.content.trim())

  if (failed && hasContent('stderr')) return 'stderr'
  return chunks.find((chunk) => chunk.content.trim())?.stream ?? chunks[0]?.stream
}

interface Props {
  runId?: string
  chunks: LogChunk[]
  /** Run 失败时优先打开 stderr，直接把诊断入口放在用户眼前。 */
  failed?: boolean
}

/** 标准输出与标准错误；后端返回前已完成已知 Secret 明文抹除。 */
export function RunLogPanel({ runId, chunks, failed = false }: Props) {
  const [stream, setStream] = useState<LogStream | undefined>(() => defaultStream(chunks, failed))
  const [downloading, setDownloading] = useState<'stdout' | 'stderr' | 'combined' | null>(null)
  const [downloadError, setDownloadError] = useState(false)
  const failureStreamSelected = useRef(false)
  const active = chunks.find((chunk) => chunk.stream === stream) ?? chunks[0]

  const download = async (selected: 'stdout' | 'stderr' | 'combined') => {
    if (!runId) return
    setDownloading(selected)
    setDownloadError(false)
    try {
      await api.downloadLogs(runId, selected)
    } catch {
      setDownloadError(true)
    } finally {
      setDownloading(null)
    }
  }

  useEffect(() => {
    if (!failed) {
      failureStreamSelected.current = false
      return
    }
    if (
      failureStreamSelected.current ||
      !chunks.some((chunk) => chunk.stream === 'stderr' && chunk.content.trim())
    ) {
      return
    }
    failureStreamSelected.current = true
    setStream('stderr')
  }, [chunks, failed])

  if (!active) {
    return <Text className={styles.muted}>这个 Run 还没有日志输出。</Text>
  }

  return (
    <div className={styles.logPanel}>
      <div className={styles.logToolbar}>
        <SegmentedControl
          aria-label="Run 日志输出"
          size="small"
          onChange={(index) => setStream(chunks[index]?.stream)}
        >
          {chunks.map((chunk) => (
            <SegmentedControl.Button
              key={chunk.stream}
              selected={active.stream === chunk.stream}
              aria-controls="run-log-console"
            >
              {chunk.stream === 'stdout' ? '标准输出' : '标准错误'}
            </SegmentedControl.Button>
          ))}
        </SegmentedControl>
        <Button
          leadingVisual={DownloadIcon}
          size="small"
          loading={downloading === 'stdout'}
          disabled={downloading !== null}
          onClick={() => void download('stdout')}
        >
          下载标准输出
        </Button>
        <Button
          leadingVisual={DownloadIcon}
          size="small"
          loading={downloading === 'stderr'}
          disabled={downloading !== null}
          onClick={() => void download('stderr')}
        >
          下载标准错误
        </Button>
        <Button
          leadingVisual={DownloadIcon}
          size="small"
          loading={downloading === 'combined'}
          disabled={downloading !== null}
          onClick={() => void download('combined')}
        >
          下载完整日志
        </Button>
      </div>
      {downloadError ? (
        <Banner variant="critical">
          <Banner.Title>日志下载失败</Banner.Title>
        </Banner>
      ) : null}
      {active.truncated ? (
        <Banner variant="warning">
          <Banner.Title>日志内容不完整</Banner.Title>
          <Banner.Description>日志过长，这里只显示尾部内容。</Banner.Description>
        </Banner>
      ) : null}
      {active.content.trim() ? (
        <CodeViewer
          id="run-log-console"
          content={active.content}
          ariaLabel={`${active.stream} 日志`}
        />
      ) : (
        <div className={styles.emptyInline}>这一路输出目前是空的。</div>
      )}
    </div>
  )
}
