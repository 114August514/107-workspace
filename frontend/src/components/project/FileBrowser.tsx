import { FileDirectoryIcon, FileIcon, HomeIcon, PlusIcon, UploadIcon } from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Button as PrimerButton,
  ConfirmationDialog,
  Link as PrimerLink,
} from '@primer/react'
import { Alert, Button, Drawer, Form, Input, Space, Tag, message } from 'antd'
import { useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { can } from '../../api/types'
import type { FileContent, Project, ProjectFile, ProjectVersionDetail } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { formatBytes, formatRelative } from '../../utils/format'
import { AsyncSection } from '../common/AsyncSection'
import { ReadmePanel } from './ReadmePanel'
import styles from './FileBrowser.module.css'

interface Props {
  projectId: string
  /** Current Project authority; undefined while the detail request is pending. */
  access: Project | undefined
  onChanged: () => void
  currentPath?: string
  basePath?: string
  version?: ProjectVersionDetail
  contextControls?: ReactNode
}

/** 当前目录级动作；文件对象操作位于文件查看页。 */
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
  rename: { title: '重命名目录', label: '新路径', extra: '目录会连同其中所有文件一起移动。' },
  copy: { title: '复制目录', label: '目标路径', extra: '目标已存在的同路径文件会被覆盖。' },
}

interface FileTreeNode {
  key: string
  path: string
  isDirectory: boolean
  file?: ProjectFile
  children?: FileTreeNode[]
}

/** ProjectFile only stores files; derive the current directory's direct children. */
function projectFileTree(files: ProjectFile[], currentPath: string): FileTreeNode[] {
  const prefix = currentPath ? `${currentPath}/` : ''
  const directories = new Map<string, FileTreeNode>()
  const entries: FileTreeNode[] = []

  for (const file of [...files].sort((left, right) => left.path.localeCompare(right.path))) {
    if (!file.path.startsWith(prefix)) continue
    const relative = file.path.slice(prefix.length)
    if (!relative || relative === '.gitkeep') continue
    const [first, ...rest] = relative.split('/')
    if (rest.length > 0) {
      const path = `${prefix}${first}`
      if (!directories.has(path)) {
        const directory = { key: `directory:${path}`, path, isDirectory: true }
        directories.set(path, directory)
        entries.push(directory)
      }
      continue
    }
    entries.push({ key: `file:${file.path}`, path: file.path, isDirectory: false, file })
  }
  return entries.sort((left, right) => {
    if (left.isDirectory !== right.isDirectory) return left.isDirectory ? -1 : 1
    return left.path.localeCompare(right.path)
  })
}

export function FileBrowser({
  projectId,
  access,
  onChanged,
  currentPath = '',
  basePath = `/projects/${projectId}/files`,
  version,
  contextControls,
}: Props) {
  const readOnly = version !== undefined
  const canWrite = !readOnly && can(access, 'project.content.write')
  const navigate = useNavigate()
  const files = useAsync<ProjectFile[]>(
    () =>
      version
        ? Promise.resolve(version.files.map((file) => ({ ...file, updated_at: null })))
        : api.listFiles(projectId),
    [projectId, version?.id],
  )
  const tree = useMemo(
    () => projectFileTree(files.data ?? [], currentPath),
    [files.data, currentPath],
  )
  const [prompt, setPrompt] = useState<PathPrompt | null>(null)
  const [promptForm] = Form.useForm<{ path: string }>()
  const [uploads, setUploads] = useState<UploadTask[]>([])
  const [deleteDirectoryOpen, setDeleteDirectoryOpen] = useState(false)
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

  const openFile = (path: string) => {
    const encodedPath = path.split('/').map(encodeURIComponent).join('/')
    navigate(`${basePath}/file/${encodedPath}`)
  }

  const readmePath = currentPath ? `${currentPath}/README.md` : 'README.md'
  const readmeEntry = files.data?.find((file) => file.path === readmePath)
  const readme = useAsync<FileContent | null>(() => {
    if (!readmeEntry) return Promise.resolve(null)
    return version
      ? api.readVersionFile(version.id, readmePath)
      : api.readFile(projectId, readmePath)
  }, [projectId, version?.id, readmePath, readmeEntry?.content_hash])

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

  const deleteDirectory = async () => {
    try {
      await api.deletePath(projectId, currentPath)
      setDeleteDirectoryOpen(false)
      refresh()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const directoryHref = (path: string) =>
    `${basePath}${path ? `/tree/${path.split('/').map(encodeURIComponent).join('/')}` : ''}`
  const currentSegments = currentPath ? currentPath.split('/') : []
  const currentName = (path: string) => path.split('/').at(-1) ?? path
  const breadcrumb = currentPath ? (
    <nav className={styles.breadcrumb} aria-label="文件路径">
      <Link to={directoryHref('')} aria-label="返回 Project 文件根目录">
        <HomeIcon size={16} />
      </Link>
      {currentSegments.map((segment, index) => {
        const path = currentSegments.slice(0, index + 1).join('/')
        return (
          <span key={path}>
            <span aria-hidden> / </span>
            <Link to={directoryHref(path)}>{segment}</Link>
          </span>
        )
      })}
    </nav>
  ) : null
  const rows = tree.map((node) => (
    <tr key={node.key}>
      <td className={styles.nameCell}>
        {node.isDirectory ? (
          <PrimerLink as={Link} to={directoryHref(node.path)} className={styles.fileLink}>
            <FileDirectoryIcon size={16} />
            {currentName(node.path)}
          </PrimerLink>
        ) : (
          <button type="button" className={styles.fileLink} onClick={() => openFile(node.path)}>
            <FileIcon size={16} />
            {currentName(node.path)}
          </button>
        )}
      </td>
      <td className={styles.metaCell}>{node.file ? formatBytes(node.file.size) : '—'}</td>
      <td className={styles.metaCell}>{node.file ? formatRelative(node.file.updated_at) : '—'}</td>
    </tr>
  ))
  const fileContext = version ? (
    <div className={styles.fileContext}>
      <Link to={directoryHref('')} className={styles.refControl}>
        {version.label} · 只读
      </Link>
    </div>
  ) : null
  const uploadMenu = canWrite ? (
    <ActionMenu>
      <ActionMenu.Button leadingVisual={PlusIcon}>添加文件</ActionMenu.Button>
      <ActionMenu.Overlay align="end" width="auto">
        <ActionList>
          <ActionList.Item
            onSelect={() => {
              promptForm.resetFields()
              setPrompt({ mode: 'new-file' })
            }}
          >
            新建文件
          </ActionList.Item>
          <ActionList.Item
            onSelect={() => {
              promptForm.resetFields()
              setPrompt({ mode: 'mkdir' })
            }}
          >
            新建目录
          </ActionList.Item>
          <ActionList.Item onSelect={() => archiveInputRef.current?.click()}>
            上传压缩包（zip）
          </ActionList.Item>
        </ActionList>
      </ActionMenu.Overlay>
    </ActionMenu>
  ) : null
  const directoryActions =
    canWrite && currentPath ? (
      <ActionMenu>
        <ActionMenu.Button>目录操作</ActionMenu.Button>
        <ActionMenu.Overlay align="end" width="auto">
          <ActionList>
            <ActionList.Item
              onSelect={() => {
                promptForm.setFieldsValue({ path: currentPath })
                setPrompt({ mode: 'rename', source: currentPath })
              }}
            >
              重命名目录
            </ActionList.Item>
            <ActionList.Item
              onSelect={() => {
                promptForm.setFieldsValue({ path: `${currentPath}-copy` })
                setPrompt({ mode: 'copy', source: currentPath })
              }}
            >
              复制目录
            </ActionList.Item>
            <ActionList.Item variant="danger" onSelect={() => setDeleteDirectoryOpen(true)}>
              删除目录
            </ActionList.Item>
          </ActionList>
        </ActionMenu.Overlay>
      </ActionMenu>
    ) : null
  const failedUploads = uploads.filter((task) => task.status !== 'success')

  return (
    <div className={styles.fileSurface}>
      <div className={styles.directoryToolbar}>
        {contextControls}
        {fileContext}
        {canWrite && (
          <div className={styles.fileToolbar}>
            <PrimerButton leadingVisual={UploadIcon} onClick={() => fileInputRef.current?.click()}>
              上传文件
            </PrimerButton>
            {uploadMenu}
            {directoryActions}
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
          </div>
        )}
      </div>
      {breadcrumb}
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
                    task.status === 'success' ? 'green' : task.status === 'failed' ? 'red' : 'blue'
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
      <AsyncSection
        loading={files.loading}
        error={files.error}
        empty={(files.data ?? []).length === 0}
        emptyText={
          canWrite ? '还没有文件。先新建一个，再保存 Project Version。' : '这个 Project 还没有文件'
        }
      >
        <table className={styles.fileTable} aria-label="文件列表">
          <thead>
            <tr>
              <th scope="col">名称</th>
              <th scope="col" className={styles.metaCell}>
                大小
              </th>
              <th scope="col" className={styles.metaCell}>
                最近修改
              </th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </AsyncSection>
      {readmeEntry && (
        <AsyncSection loading={readme.loading} error={readme.error}>
          {readme.data && (
            <ReadmePanel
              content={readme.data.content}
              fileHref={`${basePath}/file/${readmePath
                .split('/')
                .map(encodeURIComponent)
                .join('/')}`}
            />
          )}
        </AsyncSection>
      )}
      {deleteDirectoryOpen && (
        <ConfirmationDialog
          title={`删除目录“${currentPath}”？`}
          onClose={(gesture) => {
            if (gesture === 'confirm') void deleteDirectory()
            else setDeleteDirectoryOpen(false)
          }}
          confirmButtonContent="删除目录"
          confirmButtonType="danger"
        >
          删除后，该目录中的文件也会从 Working State 删除。
        </ConfirmationDialog>
      )}
      <PathPromptDrawer
        prompt={prompt}
        form={promptForm}
        onCancel={() => setPrompt(null)}
        onOk={submitPrompt}
      />
    </div>
  )
}

/** 当前目录级的新建文件与新建目录表单。 */
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
