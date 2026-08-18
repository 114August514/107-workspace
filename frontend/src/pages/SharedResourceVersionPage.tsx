import { TagIcon } from '@primer/octicons-react'
import { Banner, Breadcrumbs, Dialog, Spinner, Text } from '@primer/react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type {
  SharedResourceDetail,
  SharedResourceVersionDetail,
  SharedResourceVersionFile,
  Workspace,
} from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { PrimerMono } from '../components/primer/PrimerMono'
import { PrimerStack } from '../components/primer/PrimerStack'
import { previewKind } from '../components/sharedresource/previewKind'
import styles from '../components/sharedresource/sharedResource.module.css'
import { PrimerRoot } from '../primer/setup'
import { formatBytes, formatTime } from '../utils/format'

export function SharedResourceVersionPage() {
  const { versionId = '' } = useParams()
  const version = useAsync<SharedResourceVersionDetail>(
    () => api.getSharedResourceVersion(versionId),
    [versionId],
  )
  const resource = useAsync<SharedResourceDetail | undefined>(
    async () => (version.data ? api.getSharedResource(version.data.shared_resource_id) : undefined),
    [version.data?.shared_resource_id],
  )
  // 面包屑要回到所属工作区的「共享资源」深链路，所以也得加载工作区。
  const workspace = useAsync<Workspace | undefined>(
    async () =>
      resource.data?.owner_workspace_id
        ? api.getWorkspace(resource.data.owner_workspace_id)
        : undefined,
    [resource.data?.owner_workspace_id],
  )

  // 文件预览：点击即挂载 Dialog，再在内部走加载/成功/失败切换。
  // 不能只在请求成功后才挂载 Dialog——那样 loading 基本看不见，失败时 Dialog 干脆不出现。
  // 按扩展名分流：文本走 text/plain 接口；图片和判不了的类型取原始字节
  //（content 接口会把二进制损坏），图片内联渲染，判不了的提供下载。
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

  const isPlatform = resource.data?.is_platform_owned ?? false
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
    <PrimerRoot>
      <PrimerStack gap="large">
        <AsyncState loading={version.loading} error={normalizeError(version.error)}>
          {version.data && (
            <header className={styles.header}>
              {/* 与资源详情页同一页头式样：面包屑一行，标题（图标 + h1）换行。 */}
              <Breadcrumbs>
                <Breadcrumbs.Item as={Link} to="/">
                  首页
                </Breadcrumbs.Item>
                {isPlatform ? (
                  // 平台资源没有所属工作区，面包屑这一段就只显示「平台」。
                  <Breadcrumbs.Item>平台</Breadcrumbs.Item>
                ) : workspace.data ? (
                  <Breadcrumbs.Item as={Link} to={`/workspaces/${workspace.data.id}`}>
                    {workspace.data.name}
                  </Breadcrumbs.Item>
                ) : null}
                <Breadcrumbs.Item
                  as={Link}
                  to={`/workspaces/${workspace.data?.id ?? ''}/shared-resources`}
                >
                  共享资源
                </Breadcrumbs.Item>
                {resource.data && (
                  <Breadcrumbs.Item as={Link} to={`/shared-resources/${resource.data.id}`}>
                    {resource.data.name}
                  </Breadcrumbs.Item>
                )}
              </Breadcrumbs>
              <div className={styles.titleRow}>
                <TagIcon className={styles.titleIcon} size={24} />
                <h1 className={styles.title}>{version.data.label}</h1>
              </div>
              <Text as="p" className={styles.headerDescription}>
                {version.data.description || '这个版本没有填写说明。'}
              </Text>
            </header>
          )}
        </AsyncState>

        {version.data && (
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
        )}

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
    </PrimerRoot>
  )
}
