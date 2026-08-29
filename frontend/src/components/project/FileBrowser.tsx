import {
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FolderOutlined,
  FileAddOutlined,
  FolderAddOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useRef, useState } from 'react'

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

/** 路径输入抽屉的四种用途。rename/copy 带源路径，其余只收一个目标路径。 */
type PathPromptMode = 'new-file' | 'mkdir' | 'rename' | 'copy'

interface PathPrompt {
  mode: PathPromptMode
  source?: string
}

interface UploadTask {
  key: string
  name: string
  status: 'uploading' | 'success' | 'failed'
  detail?: string
}

const PATH_PROMPT_COPY: Record<PathPromptMode, { title: string; label: string; extra?: string }> = {
  'new-file': {
    title: '新建文件',
    label: '文件路径',
    extra: '相对于 Project 根目录，例如 src/train.py',
  },
  mkdir: {
    title: '新建目录',
    label: '目录路径',
    extra: '空目录以 .gitkeep 占位文件存在，这样才能出现在列表里并保存进版本。',
  },
  rename: { title: '重命名 / 移动', label: '新路径', extra: '目录会连同其中所有文件一起移动。' },
  copy: { title: '复制', label: '目标路径', extra: '目标已存在的同路径文件会被覆盖。' },
}

interface FileTreeNode {
  key: string
  path: string
  isDirectory: boolean
  file?: ProjectFile
  children?: FileTreeNode[]
}

/** ProjectFile only stores files; derive directory rows from every path prefix. */
function projectFileTree(files: ProjectFile[]): FileTreeNode[] {
  const roots: FileTreeNode[] = []
  const directories = new Map<string, FileTreeNode>()

  for (const file of [...files].sort((left, right) => left.path.localeCompare(right.path))) {
    const parts = file.path.split('/')
    let children = roots
    for (let index = 0; index < parts.length - 1; index += 1) {
      const path = parts.slice(0, index + 1).join('/')
      let directory = directories.get(path)
      if (!directory) {
        directory = { key: `directory:${path}`, path, isDirectory: true, children: [] }
        directories.set(path, directory)
        children.push(directory)
      }
      children = directory.children ?? []
    }

    if (parts.at(-1) !== '.gitkeep') {
      children.push({
        key: `file:${file.path}`,
        path: file.path,
        isDirectory: false,
        file,
      })
    }
  }
  return roots
}

/** Project Working Tree：可编辑的当前文件状态。 */
export function FileBrowser({ projectId, access, onChanged }: Props) {
  const canWrite = can(access, 'project.content.write')
  const files = useAsync<ProjectFile[]>(() => api.listFiles(projectId), [projectId])
  const tree = useMemo(() => projectFileTree(files.data ?? []), [files.data])
  const [editing, setEditing] = useState<{
    path: string
    content: string
    /** 后端只返回了前 256 KB。截断的内容**不能存回去**。 */
    truncated: boolean
  } | null>(null)
  const [saving, setSaving] = useState(false)
  const [prompt, setPrompt] = useState<PathPrompt | null>(null)
  const [promptForm] = Form.useForm<{ path: string }>()
  const [uploads, setUploads] = useState<UploadTask[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const archiveInputRef = useRef<HTMLInputElement>(null)

  const refresh = () => {
    files.reload()
    onChanged()
  }

  const patchUpload = (key: string, patch: Partial<UploadTask>) => {
    setUploads((current) =>
      current.map((task) => (task.key === key ? { ...task, ...patch } : task)),
    )
  }

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
      refresh()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  /** 上传入口统一走这里：逐个文件一个请求，成败互不影响。 */
  const uploadOneByOne = async (picked: File[]) => {
    if (!canWrite || picked.length === 0) return
    const batch = picked.map((file, index) => ({
      key: `${file.name}-${file.size}-${index}`,
      name: file.name,
      status: 'uploading' as const,
    }))
    setUploads((current) => [...current, ...batch])

    for (const [index, task] of batch.entries()) {
      const file = picked[index]
      if (!file) continue
      try {
        await api.uploadFiles(projectId, [file])
        patchUpload(task.key, { status: 'success' })
      } catch (error) {
        patchUpload(task.key, { status: 'failed', detail: (error as Error).message })
      }
    }
    refresh()
  }

  const uploadArchive = async (picked: FileList | null) => {
    const archive = picked?.[0]
    if (!canWrite || !archive) return
    const key = `archive-${archive.name}-${archive.size}`
    setUploads((current) => [...current, { key, name: archive.name, status: 'uploading' }])
    try {
      await api.uploadArchive(projectId, archive)
      patchUpload(key, { status: 'success' })
      refresh()
    } catch (error) {
      // 整体拒绝时后端不做部分展开，工作区保持原样，可以直接换包重传。
      patchUpload(key, { status: 'failed', detail: (error as Error).message })
    }
  }

  const submitPrompt = async () => {
    if (!prompt) return
    const values = await promptForm.validateFields()
    try {
      switch (prompt.mode) {
        case 'new-file':
          await api.writeFile(projectId, values.path, '')
          break
        case 'mkdir':
          await api.createDirectory(projectId, values.path)
          break
        case 'rename':
          await api.movePath(projectId, prompt.source ?? '', values.path)
          break
        case 'copy':
          await api.copyPath(projectId, prompt.source ?? '', values.path)
          break
      }
      promptForm.resetFields()
      setPrompt(null)
      refresh()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const removePath = async (path: string) => {
    try {
      await api.deletePath(projectId, path)
      message.success(`已删除 ${path}`)
      refresh()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const downloadFile = async (path: string) => {
    try {
      await api.downloadFile(projectId, path)
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<FileTreeNode> = [
    {
      title: '路径',
      dataIndex: field<FileTreeNode>('path'),
      render: (path: string, node) =>
        node.isDirectory ? (
          <Space size="small">
            <FolderOutlined />
            <Typography.Text>{path}</Typography.Text>
          </Space>
        ) : (
          <Button type="link" size="small" onClick={() => openFile(path)}>
            {path}
          </Button>
        ),
    },
    {
      title: '大小',
      width: 110,
      render: (_, node) => (node.file ? formatBytes(node.file.size) : '—'),
    },
    {
      title: '修改时间',
      width: 130,
      render: (_, node) => (node.file ? formatRelative(node.file.updated_at) : '—'),
    },
    {
      title: '操作',
      width: 260,
      key: 'actions',
      render: (_, node) =>
        !canWrite ? null : (
          <Space size={0}>
            {node.file && (
              <Button
                type="link"
                size="small"
                icon={<DownloadOutlined />}
                onClick={() => downloadFile(node.path)}
              >
                下载
              </Button>
            )}
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                promptForm.setFieldsValue({ path: node.path })
                setPrompt({ mode: 'rename', source: node.path })
              }}
            >
              改名
            </Button>
            <Button
              type="link"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                promptForm.setFieldsValue({ path: `${node.path}-copy` })
                setPrompt({ mode: 'copy', source: node.path })
              }}
            >
              复制
            </Button>
            <Popconfirm
              title={`删除 ${node.path}？`}
              description="目录会连同其中所有文件一起删除。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => removePath(node.path)}
            >
              <Button
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                aria-label={`删除 ${node.path}`}
              />
            </Popconfirm>
          </Space>
        ),
    },
  ]

  const failedUploads = uploads.filter((task) => task.status !== 'success')

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {canWrite && (
        <>
          <Space wrap>
            <Button icon={<UploadOutlined />} onClick={() => fileInputRef.current?.click()}>
              上传文件
            </Button>
            <Button icon={<UploadOutlined />} onClick={() => archiveInputRef.current?.click()}>
              上传压缩包（zip）
            </Button>
            <Button
              icon={<FolderAddOutlined />}
              onClick={() => {
                promptForm.resetFields()
                setPrompt({ mode: 'mkdir' })
              }}
            >
              新建目录
            </Button>
            <Button
              icon={<FileAddOutlined />}
              onClick={() => {
                promptForm.resetFields()
                setPrompt({ mode: 'new-file' })
              }}
            >
              新建文件
            </Button>
            {/* 隐藏 input 换取对上传行为的完全控制；label 由上面的按钮承担。 */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(event) => {
                void uploadOneByOne(Array.from(event.target.files ?? []))
                event.target.value = ''
              }}
            />
            <input
              ref={archiveInputRef}
              type="file"
              accept=".zip,application/zip"
              hidden
              onChange={(event) => {
                void uploadArchive(event.target.files)
                event.target.value = ''
              }}
            />
          </Space>

          {uploads.length > 0 && (
            <Alert
              type={failedUploads.length > 0 ? 'warning' : 'success'}
              showIcon
              message={
                <Space wrap size={[8, 8]}>
                  {uploads.map((task) => (
                    <Tag
                      key={task.key}
                      color={
                        task.status === 'success'
                          ? 'green'
                          : task.status === 'failed'
                            ? 'red'
                            : 'blue'
                      }
                    >
                      {task.name}
                      {task.status === 'uploading' && '（上传中）'}
                      {task.status === 'failed' && `：${task.detail ?? '失败'}`}
                    </Tag>
                  ))}
                </Space>
              }
              action={
                <Button size="small" onClick={() => setUploads([])}>
                  清除记录
                </Button>
              }
            />
          )}
        </>
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
          rowKey="key"
          size="small"
          dataSource={tree}
          columns={columns}
          defaultExpandAllRows
          pagination={false}
          scroll={{ x: true }}
        />
      </AsyncSection>

      <PathPromptDrawer
        prompt={prompt}
        form={promptForm}
        onCancel={() => setPrompt(null)}
        onOk={submitPrompt}
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

/** 新建 / 建目录 / 改名 / 复制共用的小抽屉，差别只在文案和提交动作。 */
function PathPromptDrawer({
  prompt,
  form,
  onCancel,
  onOk,
}: {
  prompt: PathPrompt | null
  form: ReturnType<typeof Form.useForm<{ path: string }>>[0]
  onCancel: () => void
  onOk: () => void
}) {
  const copy = prompt ? PATH_PROMPT_COPY[prompt.mode] : null
  return (
    <Drawer
      open={prompt !== null}
      title={copy?.title}
      placement="right"
      width={420}
      onClose={onCancel}
    >
      {prompt && (
        <Form form={form} layout="vertical" onFinish={onOk}>
          {prompt.mode === 'rename' && (
            <Form.Item label="原路径">
              <Input value={prompt.source} disabled />
            </Form.Item>
          )}
          {prompt.mode === 'copy' && (
            <Form.Item label="源路径">
              <Input value={prompt.source} disabled />
            </Form.Item>
          )}
          <Form.Item
            name="path"
            label={copy?.label}
            rules={[{ required: true, message: '请填写路径' }]}
            extra={copy?.extra}
          >
            <Input placeholder="src/train.py" />
          </Form.Item>
          <Space>
            <Button type="primary" onClick={onOk}>
              确定
            </Button>
            <Button onClick={onCancel}>取消</Button>
          </Space>
        </Form>
      )}
    </Drawer>
  )
}
