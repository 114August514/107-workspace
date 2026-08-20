import { TagIcon } from '@primer/octicons-react'
import { Banner, Dialog, Spinner, Text } from '@primer/react'
import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type { SharedResourceVersionDetail, SharedResourceVersionFile } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { normalizeError } from '../common/asyncStateError'
import { PrimerListCard } from '../primer/PrimerListCard'
import { PrimerMono, PrimerRelativeTime } from '../primer/PrimerMono'
import { PrimerStack } from '../primer/PrimerStack'
import { previewKind } from './previewKind'
import styles from './sharedResource.module.css'
import { formatBytes, formatTime } from '../../utils/format'

interface Props {
  versionId: string
}

/**
 * 版本详情主体：tag 行 + 元数据 + 文件表 + 文件预览 Dialog。
 *
 * 只依赖 versionId，供两处复用：独立版本详情页（深链路入口）与
 * 资源详情页右侧分栏。预览按扩展名分流：文本走 text/plain 接口，
 * 图片和判不了的类型取原始字节——content 接口会把二进制损坏。
 */
export function SharedResourceVersionBody({ versionId }: Props) {
  const version = useAsync<SharedResourceVersionDetail>(
    () => api.getSharedResourceVersion(versionId),
    [versionId],
  )

  // 文件预览：点击即挂载 Dialog，再在内部走加载/成功/失败切换。
  // 不能只在请求成功后才挂载 Dialog——那样 loading 基本看不见，失败时 Dialog 干脆不出现。
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [previewContent, setPreviewContent] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')

  useEffect(() => {
    if (!selectedPath) return
    let alive = true
    setPreviewLoading(true)
    setPreviewError('')
    if (previewKind(selectedPath) === 'text') {
      api
        .readSharedResourceVersionFile(versionId, selectedPath)
        .then((content) => {
          if (alive) setPreviewContent(content)
        })
        .catch((err: Error) => {
          if (alive) setPreviewError(err.message)
        })
        .finally(() => {
          if (alive) setPreviewLoading(false)
        })
    } else {
      api
        .downloadSharedResourceVersionFile(versionId, selectedPath)
        .then((blob) => {
          if (alive) setPreviewUrl(URL.createObjectURL(blob))
        })
        .catch((err: Error) => {
          if (alive) setPreviewError(err.message)
        })
        .finally(() => {
          if (alive) setPreviewLoading(false)
        })
    }
    return () => {
      alive = false
    }
  }, [versionId, selectedPath])

  // object URL 用完即回收，换文件/关 Dialog 都不留泄漏。
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  const closePreview = () => {
    setSelectedPath(null)
    setPreviewContent('')
    setPreviewUrl('')
    setPreviewError('')
  }

  const kind = selectedPath !== null ? previewKind(selectedPath) : 'text'

  const meta = version.data
    ? [
        { label: '版本号', value: <PrimerMono>{`v${version.data.sequence}`}</PrimerMono> },
        { label: '发布者', value: <PrimerMono>{version.data.created_by}</PrimerMono> },
        { label: '文件数', value: <PrimerMono>{String(version.data.file_count)}</PrimerMono> },
        { label: '总大小', value: formatBytes(version.data.total_size) },
        { label: '发布时间', value: formatTime(version.data.created_at) },
      ]
    : []

  return (
    <PrimerStack gap="large">
      <AsyncState loading={version.loading} error={normalizeError(version.error)}>
        {version.data && (
          <>
            <div className={styles.versionTagRow}>
              <TagIcon className={styles.titleIcon} size={24} />
              <h2 className={styles.versionTitle}>{version.data.label}</h2>
              <Text size="small" className={styles.desc}>
                <PrimerRelativeTime value={version.data.created_at} />
              </Text>
            </div>
            <table className={styles.metaTable}>
              <tbody>
                {meta.map((row) => (
                  <tr key={row.label} className={styles.metaRow}>
                    <td className={styles.metaLabel}>{row.label}</td>
                    <td className={styles.metaCell}>{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </AsyncState>

      <PrimerListCard title="文件">
        <AsyncState
          loading={version.loading}
          error={normalizeError(version.error)}
          empty={version.data !== undefined && (version.data.files ?? []).length === 0}
          emptyText="这个版本没有文件。"
          emptyDescription="发布版本时上传的文件会列在这里。"
        >
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>路径</th>
                <th className={`${styles.th} ${styles.colSize}`}>大小</th>
              </tr>
            </thead>
            <tbody>
              {(version.data?.files ?? []).map((file: SharedResourceVersionFile) => (
                <tr key={file.path} className={styles.row}>
                  <td className={styles.td}>
                    <button
                      type="button"
                      className={styles.fileButton}
                      onClick={() => setSelectedPath(file.path)}
                    >
                      {file.path}
                    </button>
                  </td>
                  <td className={styles.td}>
                    <Text size="small" className={styles.desc}>
                      {formatBytes(file.size)}
                    </Text>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </AsyncState>
      </PrimerListCard>

      {selectedPath !== null && (
        <Dialog
          onClose={closePreview}
          title={selectedPath}
          width="large"
          footerButtons={[{ content: '关闭', onClick: closePreview, buttonType: 'default' }]}
        >
          <Text size="small" className={styles.previewNote}>
            版本内容不可变，这是版本发布时存下的快照，只能查看，不能修改。
          </Text>
          {previewLoading ? (
            <div role="status" className={styles.previewLoading}>
              <Spinner size="small" srText="正在读取文件" />
              <Text size="small">正在读取文件…</Text>
            </div>
          ) : previewError ? (
            <Banner variant="critical">
              <Banner.Title>文件预览失败。</Banner.Title>
              <Banner.Description>{previewError}</Banner.Description>
            </Banner>
          ) : kind === 'image' ? (
            <img
              src={previewUrl}
              alt={selectedPath}
              className={styles.previewImage}
              onError={() => setPreviewError('图片加载失败。')}
            />
          ) : kind === 'text' ? (
            <pre className={styles.previewCode}>{previewContent}</pre>
          ) : (
            // 判不了的类型不硬猜内容，像 GitHub 一样明说不可预览，给出下载出路。
            <div className={styles.previewUnknown}>
              <Text>暂时无法预览这个文件。</Text>
              <Text size="small" className={styles.desc}>
                平台支持内联预览文本和图片，其它类型可以下载后查看。
              </Text>
              {previewUrl && (
                <a
                  className={styles.previewDownload}
                  href={previewUrl}
                  download={selectedPath.split('/').pop()}
                >
                  下载文件
                </a>
              )}
            </div>
          )}
        </Dialog>
      )}
    </PrimerStack>
  )
}
