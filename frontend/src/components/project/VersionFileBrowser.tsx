import { Alert, Drawer, Input, Space, Spin, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import { api } from '../../api/client'
import type { ProjectVersionFile } from '../../api/types'
import { field } from '../../utils/field'
import { formatBytes } from '../../utils/format'

interface Props {
  versionId: string
  files: ProjectVersionFile[]
}

/**
 * 版本文件浏览（只读）。
 *
 * Version 是不可变快照，这里的文件只能看不能改。复用 FileBrowser 的
 * Drawer 视觉模式，但去掉所有写操作——没有保存按钮、没有新建按钮。
 */
export function VersionFileBrowser({ versionId, files }: Props) {
  const [viewing, setViewing] = useState<{
    path: string
    content: string
    truncated: boolean
  } | null>(null)
  const [loading, setLoading] = useState(false)

  const openFile = async (path: string) => {
    setLoading(true)
    try {
      const file = await api.readVersionFile(versionId, path)
      setViewing({ path, content: file.content, truncated: file.truncated })
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const columns: ColumnsType<ProjectVersionFile> = [
    { title: '路径', dataIndex: field<ProjectVersionFile>('path') },
    {
      title: '大小',
      dataIndex: field<ProjectVersionFile>('size'),
      width: 100,
      render: formatBytes,
    },
    {
      title: '操作',
      width: 80,
      key: 'view',
      render: (_, file) => (
        <Typography.Link onClick={() => openFile(file.path)}>查看</Typography.Link>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Table rowKey="path" size="small" dataSource={files} columns={columns} pagination={false} />

      <Drawer
        open={viewing !== null}
        title={
          <Space>
            {viewing?.path}
            <Tag color="default">只读</Tag>
          </Space>
        }
        width={720}
        onClose={() => setViewing(null)}
        extra={<Typography.Link onClick={() => setViewing(null)}>关闭</Typography.Link>}
      >
        <Spin spinning={loading}>
          {viewing?.truncated && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="内容已截断"
              description="这个文件超过 256 KiB，只显示了开头一部分。"
            />
          )}
          <Input.TextArea
            readOnly
            value={viewing?.content ?? ''}
            autoSize={{ minRows: 24, maxRows: 40 }}
            style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 13 }}
          />
        </Spin>
      </Drawer>
    </Space>
  )
}
