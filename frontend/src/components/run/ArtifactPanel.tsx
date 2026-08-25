import { DownloadIcon, PackageIcon } from '@primer/octicons-react'
import { Banner, Button, Label, Text } from '@primer/react'
import { Blankslate } from '@primer/react/experimental'
import { useState } from 'react'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import type { Artifact, ArtifactEntry } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { formatBytes, formatTime } from '../../utils/format'
import { AsyncState } from '../common/AsyncState'
import { PrimerListCard } from '../primer/PrimerListCard'
import styles from './run.module.css'

function ArtifactFiles({ artifact }: { artifact: Artifact }) {
  const entries = useAsync<ArtifactEntry[]>(() => api.listArtifactFiles(artifact.id), [artifact.id])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<Error | undefined>()

  const download = async (path: string) => {
    setDownloading(path)
    setDownloadError(undefined)
    try {
      await api.downloadArtifactFile(artifact.id, path)
    } catch (error) {
      setDownloadError(error as Error)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <AsyncState
      loading={entries.loading}
      loadingText="正在读取运行产物文件…"
      error={
        entries.error
          ? { ...toAsyncError(entries.error), message: '无法读取这个运行产物。' }
          : undefined
      }
      onRetry={entries.reload}
      empty={(entries.data ?? []).length === 0}
      emptyText="这个运行产物没有文件。"
    >
      {downloadError ? (
        <div className={styles.inlineBanner}>
          <Banner variant="critical">
            <Banner.Title>无法下载这个文件。</Banner.Title>
            <Banner.Description>{toAsyncError(downloadError)?.problems?.[0]}</Banner.Description>
          </Banner>
        </div>
      ) : null}
      <div className={styles.tableScroller}>
        <table className={styles.artifactTable} aria-label={`${artifact.name} 文件`}>
          <thead>
            <tr>
              <th scope="col">文件</th>
              <th scope="col">大小</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            {(entries.data ?? []).map((entry) => (
              <tr key={entry.path}>
                <td>
                  <code className={styles.inlineCode}>{entry.path}</code>
                </td>
                <td>{formatBytes(entry.size)}</td>
                <td>
                  <Button
                    size="small"
                    leadingVisual={DownloadIcon}
                    loading={downloading === entry.path}
                    disabled={downloading !== null}
                    onClick={() => void download(entry.path)}
                  >
                    下载文件
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AsyncState>
  )
}

export function ArtifactPanel({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) {
    return (
      <Blankslate narrow>
        <Blankslate.Visual>
          <PackageIcon size={24} />
        </Blankslate.Visual>
        <Blankslate.Heading>这个 Run 没有产生运行产物。</Blankslate.Heading>
      </Blankslate>
    )
  }

  return (
    <div className={styles.artifactList}>
      {artifacts.map((artifact) => (
        <PrimerListCard
          key={artifact.id}
          title={
            <span className={styles.artifactTitle}>
              {artifact.name}
              {artifact.status !== 'available' ? (
                <Label variant="attention">内容已清理</Label>
              ) : null}
            </span>
          }
          extra={
            <Text size="small" className={styles.muted}>
              {artifact.file_count} 个文件 · {formatBytes(artifact.size)} ·{' '}
              {formatTime(artifact.created_at)}
            </Text>
          }
        >
          <div className={styles.artifactMeta}>
            <code className={styles.inlineCode}>{artifact.source_path}</code>
            {artifact.description ? <Text size="small">{artifact.description}</Text> : null}
          </div>
          {artifact.status === 'available' ? (
            <ArtifactFiles artifact={artifact} />
          ) : (
            <div className={styles.emptyInline}>内容已清理；运行产物记录仍保留在 Run 历史中。</div>
          )}
        </PrimerListCard>
      ))}
    </div>
  )
}
