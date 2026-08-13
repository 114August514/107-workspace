import { Dialog, Flash, Text } from '@primer/react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type {
  SharedResourceDetail,
  SharedResourceVersionDetail,
  SharedResourceVersionFile,
} from '../api/types'
import { useAsync } from '../api/useAsync'
import { PrimerAsyncSection } from '../components/primer/PrimerAsyncSection'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { PrimerMono } from '../components/primer/PrimerMono'
import { PrimerPageHeader } from '../components/primer/PrimerPageHeader'
import { PrimerStack } from '../components/primer/PrimerStack'
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
  const [preview, setPreview] = useState<{ path: string; content: string } | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [previewError, setPreviewError] = useState('')

  const openFile = async (path: string) => {
    setLoadingPreview(true)
    setPreviewError('')
    try {
      const content = await api.readSharedResourceVersionFile(versionId, path)
      setPreview({ path, content })
    } catch (error) {
      setPreviewError((error as Error).message)
    } finally {
      setLoadingPreview(false)
    }
  }

  return (
    <PrimerStack gap="large">
      <PrimerAsyncSection loading={version.loading} error={version.error}>
        {version.data && (
          <PrimerPageHeader
            breadcrumb={[
              { title: <Link to="/">首页</Link> },
              {
                title: resource.data ? (
                  <Link to={`/shared-resources/${resource.data.id}`}>{resource.data.name}</Link>
                ) : (
                  'Shared Resource'
                ),
              },
              { title: version.data.label },
            ]}
            title={version.data.label}
            description={version.data.description || '这个版本没有填写说明'}
          />
        )}
      </PrimerAsyncSection>

      {version.data && (
        <div
          style={{
            border: '1px solid var(--borderColor-default)',
            borderRadius: 6,
            overflow: 'hidden',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid var(--borderColor-default)' }}>
                <td
                  style={{
                    padding: '8px 16px',
                    fontWeight: 500,
                    backgroundColor: 'var(--bgColor-muted)',
                    width: 140,
                  }}
                >
                  版本号
                </td>
                <td style={{ padding: '8px 16px' }}>
                  <PrimerMono>{`v${version.data.sequence}`}</PrimerMono>
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid var(--borderColor-default)' }}>
                <td
                  style={{
                    padding: '8px 16px',
                    fontWeight: 500,
                    backgroundColor: 'var(--bgColor-muted)',
                  }}
                >
                  发布者
                </td>
                <td style={{ padding: '8px 16px' }}>
                  <PrimerMono>{version.data.created_by}</PrimerMono>
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid var(--borderColor-default)' }}>
                <td
                  style={{
                    padding: '8px 16px',
                    fontWeight: 500,
                    backgroundColor: 'var(--bgColor-muted)',
                  }}
                >
                  文件数
                </td>
                <td style={{ padding: '8px 16px' }}>
                  <PrimerMono>{String(version.data.file_count)}</PrimerMono>
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid var(--borderColor-default)' }}>
                <td
                  style={{
                    padding: '8px 16px',
                    fontWeight: 500,
                    backgroundColor: 'var(--bgColor-muted)',
                  }}
                >
                  总大小
                </td>
                <td style={{ padding: '8px 16px' }}>
                  <Text size="small">{formatBytes(version.data.total_size)}</Text>
                </td>
              </tr>
              <tr>
                <td
                  style={{
                    padding: '8px 16px',
                    fontWeight: 500,
                    backgroundColor: 'var(--bgColor-muted)',
                  }}
                >
                  发布时间
                </td>
                <td style={{ padding: '8px 16px' }}>
                  <Text size="small">{formatTime(version.data.created_at)}</Text>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <PrimerListCard title="文件">
        <PrimerAsyncSection
          loading={version.loading}
          error={version.error}
          empty={(version.data?.files ?? []).length === 0}
          emptyText="这个版本没有文件"
        >
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th
                  style={{
                    textAlign: 'left',
                    padding: '8px 16px',
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--fgColor-muted)',
                    borderBottom: '1px solid var(--borderColor-default)',
                  }}
                >
                  路径
                </th>
                <th
                  style={{
                    textAlign: 'left',
                    padding: '8px 16px',
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--fgColor-muted)',
                    borderBottom: '1px solid var(--borderColor-default)',
                    width: 110,
                  }}
                >
                  大小
                </th>
              </tr>
            </thead>
            <tbody>
              {(version.data?.files ?? []).map((file: SharedResourceVersionFile) => (
                <tr
                  key={file.path}
                  style={{ borderBottom: '1px solid var(--borderColor-default)' }}
                >
                  <td style={{ padding: '8px 16px' }}>
                    <button
                      type="button"
                      onClick={() => openFile(file.path)}
                      style={{
                        border: 'none',
                        background: 'none',
                        cursor: 'pointer',
                        padding: 0,
                        color: 'var(--fgColor-accent)',
                        fontSize: 14,
                        fontFamily: 'inherit',
                      }}
                    >
                      {file.path}
                    </button>
                  </td>
                  <td style={{ padding: '8px 16px' }}>
                    <Text size="small">{formatBytes(file.size)}</Text>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </PrimerAsyncSection>
      </PrimerListCard>

      {preview !== null && (
        <Dialog
          onClose={() => {
            setPreview(null)
            setPreviewError('')
          }}
          title={preview.path}
          width="large"
          footerButtons={[
            {
              content: '关闭',
              onClick: () => {
                setPreview(null)
                setPreviewError('')
              },
              buttonType: 'default',
            },
          ]}
        >
          <Flash variant="default" style={{ marginBottom: 12 }}>
            版本内容不可变，这是版本发布时存下的快照，只能查看，不能修改。
          </Flash>
          {loadingPreview ? (
            <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
              读取中…
            </Text>
          ) : previewError ? (
            <Flash variant="danger">{previewError}</Flash>
          ) : (
            <pre
              style={{
                fontFamily: 'var(--fontFamily-mono)',
                fontSize: 13,
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {preview?.content ?? ''}
            </pre>
          )}
        </Dialog>
      )}
    </PrimerStack>
  )
}
