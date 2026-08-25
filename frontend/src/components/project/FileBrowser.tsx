import { DeleteOutlined, FileAddOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Popconfirm,
  Space,
  Table,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { Project, ProjectFile } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { formatBytes, formatRelative } from '../../utils/format'
import { AsyncSection } from '../common/AsyncSection'

interface Props {
  projectId: string
  /** Current Project authority; undefined while the detail request is pending. */
  access: Project | undefined
  onChanged: () => void
}

/** Project Working Tree：可编辑的当前文件状态。 */
export function FileBrowser({ projectId, access, onChanged }: Props) {
  const canWrite = can(access, 'project.content.write')
  const files = useAsync<ProjectFile[]>(() => api.listFiles(projectId), [projectId])
  const [editing, setEditing] = useState<{
    path: string
    content: string
    /** 后端只返回了前 256 KB。截断的内容**不能存回去**。 */
    truncated: boolean
  } | null>(null)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm<{ path: string }>()

  const openFile = async (path: string) => {
    try {
      const file = await api.readFile(projectId, path)
      setEditing({ path, content: file.content, truncated: file.truncated })
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const saveFile = async () => {
    if (!editing) return
    setSaving(true)
    try {
      await api.writeFile(projectId, editing.path, editing.content)
      message.success(`已保存 ${editing.path}`)
      setEditing(null)
      files.reload()
      onChanged()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const createFile = async () => {
    const values = await createForm.validateFields()
    try {
      await api.writeFile(projectId, values.path, '')
      createForm.resetFields()
      setCreating(false)
      files.reload()
      onChanged()
      await openFile(values.path)
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const removePath = async (path: string) => {
    try {
      await api.deletePath(projectId, path)
      message.success(`已删除 ${path}`)
      files.reload()
      onChanged()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<ProjectFile> = [
    {
      title: '路径',
      dataIndex: field<ProjectFile>('path'),
      render: (path: string) => (
        <Typography.Link onClick={() => openFile(path)}>{path}</Typography.Link>
      ),
    },
    { title: '大小', dataIndex: field<ProjectFile>('size'), width: 110, render: formatBytes },
    {
      title: '修改时间',
      dataIndex: field<ProjectFile>('updated_at'),
      width: 130,
      render: formatRelative,
    },
    {
      title: '操作',
      width: 80,
      key: 'actions',
      render: (_, file) =>
        !canWrite ? null : (
          <Popconfirm
            title={`删除 ${file.path}？`}
            okText="删除"
            cancelText="取消"
            onConfirm={() => removePath(file.path)}
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {canWrite && (
        <Space>
          <Button icon={<FileAddOutlined />} onClick={() => setCreating(true)}>
            新建文件
          </Button>
        </Space>
      )}

      <AsyncSection
        loading={files.loading}
        error={files.error}
        empty={(files.data ?? []).length === 0}
        emptyText={
          canWrite ? '还没有文件。先新建一个，再保存 Project Version。' : '这个 Project 还没有文件'
        }
      >
        <Table
          rowKey="path"
          size="small"
          dataSource={files.data ?? []}
          columns={columns}
          pagination={false}
        />
      </AsyncSection>

      <Modalish
        open={creating}
        onCancel={() => setCreating(false)}
        onOk={createFile}
        form={createForm}
      />

      <Drawer
        open={editing !== null}
        title={editing?.path}
        width={720}
        onClose={() => setEditing(null)}
        extra={
          <Space>
            <Button onClick={() => setEditing(null)}>
              {canWrite && !editing?.truncated ? '取消' : '关闭'}
            </Button>
            {/* 截断的内容不给保存按钮。存回去等于把文件裁到 256 KB，
                而且是静默发生的——用户以为自己只改了一行。 */}
            {canWrite && !editing?.truncated && (
              <Button type="primary" onClick={saveFile} loading={saving}>
                保存
              </Button>
            )}
          </Space>
        }
      >
        {editing?.truncated && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="这个文件太大，只显示了开头一部分"
            description="为了不把剩下的内容截断，这里只能查看不能保存。要修改请在本地编辑后重新上传。"
          />
        )}
        <Input.TextArea
          readOnly={!canWrite || editing?.truncated}
          value={editing?.content ?? ''}
          onChange={(event) =>
            setEditing((current) =>
              current ? { ...current, content: event.target.value } : current,
            )
          }
          autoSize={{ minRows: 24, maxRows: 40 }}
          style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 13 }}
        />
      </Drawer>
    </Space>
  )
}

/** 新建文件的小弹窗，单独抽出来让 FileBrowser 的主流程保持清爽。 */
function Modalish({
  open,
  onCancel,
  onOk,
  form,
}: {
  open: boolean
  onCancel: () => void
  onOk: () => void
  form: ReturnType<typeof Form.useForm<{ path: string }>>[0]
}) {
  return (
    <Drawer open={open} title="新建文件" placement="right" width={420} onClose={onCancel}>
      <Form form={form} layout="vertical" onFinish={onOk}>
        <Form.Item
          name="path"
          label="路径"
          rules={[{ required: true, message: '请填写文件路径' }]}
          extra="相对于 Project 根目录，例如 src/train.py"
        >
          <Input placeholder="train.py" />
        </Form.Item>
        <Space>
          <Button type="primary" onClick={onOk}>
            创建
          </Button>
          <Button onClick={onCancel}>取消</Button>
        </Space>
      </Form>
    </Drawer>
  )
}
