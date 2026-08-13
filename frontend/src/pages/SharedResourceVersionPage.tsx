import { Alert, Button, Descriptions, Drawer, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type {
  SharedResourceDetail,
  SharedResourceVersionDetail,
  SharedResourceVersionFile,
} from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncSection } from '../components/common/AsyncSection'
import { Mono } from '../components/common/Mono'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { field } from '../utils/field'
import { formatBytes, formatTime } from '../utils/format'

export function SharedResourceVersionPage() {
  const { versionId = '' } = useParams()
  const version = useAsync<SharedResourceVersionDetail>(
    () => api.getSharedResourceVersion(versionId),
    [versionId],
  )
  // 版本详情不带资源名，单独取一下父资源做面包屑和标题。
  const resource = useAsync<SharedResourceDetail | undefined>(
    async () => (version.data ? api.getSharedResource(version.data.shared_resource_id) : undefined),
    [version.data?.shared_resource_id],
  )
  const [preview, setPreview] = useState<{ path: string; content: string } | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)

  const openFile = async (path: string) => {
    setLoadingPreview(true)
    try {
      const content = await api.readSharedResourceVersionFile(versionId, path)
      setPreview({ path, content })
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setLoadingPreview(false)
    }
  }

  const fileColumns: ColumnsType<SharedResourceVersionFile> = [
    {
      title: '路径',
      dataIndex: field<SharedResourceVersionFile>('path'),
      render: (path: string) => (
        <Typography.Link onClick={() => openFile(path)}>{path}</Typography.Link>
      ),
    },
    {
      title: '大小',
      dataIndex: field<SharedResourceVersionFile>('size'),
      width: 110,
      render: formatBytes,
    },
  ]

  return (
    <Stack gap="large">
      <AsyncSection loading={version.loading} error={version.error}>
        {version.data && (
          <PageHeader
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
      </AsyncSection>

      {version.data && (
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="版本号">
            <Mono>{`v${version.data.sequence}`}</Mono>
          </Descriptions.Item>
          <Descriptions.Item label="发布者">
            <Mono>{version.data.created_by}</Mono>
          </Descriptions.Item>
          <Descriptions.Item label="文件数">
            <Mono>{String(version.data.file_count)}</Mono>
          </Descriptions.Item>
          <Descriptions.Item label="总大小">
            {formatBytes(version.data.total_size)}
          </Descriptions.Item>
          <Descriptions.Item label="发布时间" span={2}>
            {formatTime(version.data.created_at)}
          </Descriptions.Item>
        </Descriptions>
      )}

      <ListCard title="文件">
        <AsyncSection
          loading={version.loading}
          error={version.error}
          empty={(version.data?.files ?? []).length === 0}
          emptyText="这个版本没有文件"
        >
          <Table
            rowKey="path"
            size="small"
            dataSource={version.data?.files ?? []}
            columns={fileColumns}
            pagination={false}
          />
        </AsyncSection>
      </ListCard>

      <Drawer
        open={preview !== null}
        title={preview?.path}
        width={720}
        onClose={() => setPreview(null)}
        extra={<Button onClick={() => setPreview(null)}>关闭</Button>}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="版本内容不可变"
          description="这是版本发布时存下的快照，只能查看，不能修改。"
        />
        <PreviewContent content={preview?.content ?? ''} loading={loadingPreview} />
      </Drawer>
    </Stack>
  )
}

/**
 * 版本文件内容的只读预览框。
 *
 * 抽出来是为了让主页面只关心数据加载和布局——预览的空态、加载态集中在这里。
 * 内容直接展示后端返回的文本；二进制文件后端也以 text/plain 返回，
 * 预览可能乱码，但接口语义就是文本预览，更建议下载。
 */
function PreviewContent({ content, loading }: { content: string; loading: boolean }) {
  if (loading) {
    return <Typography.Text type="secondary">读取中…</Typography.Text>
  }
  return (
    <Typography.Paragraph>
      <pre
        style={{
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          fontSize: 13,
          margin: 0,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {content}
      </pre>
    </Typography.Paragraph>
  )
}
