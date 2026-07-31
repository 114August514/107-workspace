import { DownloadOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Space, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type { Artifact, ArtifactEntry } from '../../api/types'
import { formatBytes } from '../../utils/format'
import { field } from '../../utils/field'

/** 某个 Artifact 的文件列表。 */
function ArtifactFiles({ artifact }: { artifact: Artifact }) {
  const [entries, setEntries] = useState<ArtifactEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    api
      .listArtifactFiles(artifact.id)
      .then((result) => {
        if (alive) setEntries(result)
      })
      .catch((error: Error) => message.error(error.message))
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [artifact.id])

  const download = async (path: string) => {
    try {
      await api.downloadArtifactFile(artifact.id, path)
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<ArtifactEntry> = [
    { title: '文件', dataIndex: field<ArtifactEntry>('path') },
    { title: '大小', dataIndex: field<ArtifactEntry>('size'), width: 110, render: formatBytes },
    {
      title: '操作',
      width: 100,
      key: 'actions',
      render: (_, entry) => (
        <Button
          type="link"
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => download(entry.path)}
        >
          下载
        </Button>
      ),
    },
  ]

  return (
    <Table
      rowKey="path"
      size="small"
      loading={loading}
      dataSource={entries}
      columns={columns}
      pagination={false}
    />
  )
}

export function ArtifactPanel({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) {
    return <Empty description="这次 Run 没有产生 Artifact" />
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {artifacts.map((artifact) => (
        <Card
          key={artifact.id}
          size="small"
          title={
            <Space>
              <Typography.Text strong>{artifact.name}</Typography.Text>
              <Tag>{artifact.source_path}</Tag>
              {artifact.status !== 'available' && <Tag color="orange">内容已清理</Tag>}
            </Space>
          }
          extra={
            <Typography.Text type="secondary">
              {artifact.file_count} 个文件 · {formatBytes(artifact.size)}
            </Typography.Text>
          }
        >
          {artifact.status === 'available' ? (
            <ArtifactFiles artifact={artifact} />
          ) : (
            <Typography.Text type="secondary">
              内容已被清理，但这条产出记录会一直保留在历史里。
            </Typography.Text>
          )}
        </Card>
      ))}
    </Space>
  )
}
