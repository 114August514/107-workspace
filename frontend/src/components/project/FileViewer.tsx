import { DownloadIcon } from '@primer/octicons-react'
import { Button, Card, Tag, Typography } from 'antd'
import { Highlight, themes } from 'prism-react-renderer'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { can } from '../../api/types'
import type { FileContent, Project, ProjectVersionDetail } from '../../api/types'
import styles from './FileViewer.module.css'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { FileObjectActions } from './FileObjectActions'
interface Props {
  projectId: string
  access: Project | undefined
  path: string
  backHref: string
  version?: ProjectVersionDetail
  onChanged?: () => void
}
function languageForPath(path: string): string {
  const extension = path.split('.').at(-1)?.toLowerCase()
  const languages: Record<string, string> = {
    js: 'javascript',
    jsx: 'jsx',
    json: 'json',
    md: 'markdown',
    py: 'python',
    sh: 'bash',
    ts: 'typescript',
    tsx: 'tsx',
    yaml: 'yaml',
    yml: 'yaml',
  }
  return languages[extension ?? ''] ?? 'text'
}

export function FileViewer({ projectId, access, path, backHref, version, onChanged }: Props) {
  const navigate = useNavigate()
  const readOnly = version !== undefined
  const canWrite = !readOnly && can(access, 'project.content.write')
  const file = useAsync<FileContent>(
    () => (version ? api.readVersionFile(version.id, path) : api.readFile(projectId, path)),
    [projectId, version?.id, path],
  )
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (file.data) setContent(file.data.content)
  }, [file.data])

  const save = async () => {
    if (!canWrite || !file.data || file.data.truncated) return
    setSaving(true)
    try {
      await api.writeFile(projectId, path, content)
      navigate(backHref)
    } finally {
      setSaving(false)
    }
  }

  const error = toAsyncError(file.error)
  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="文件路径">
        <Link to={backHref}>Files</Link>
        <span aria-hidden> / </span>
        <span>{path}</span>
      </nav>
      <div className={styles.header}>
        <div>
          <Typography.Title level={3}>{path}</Typography.Title>
          {version && <Tag color="blue">{version.label} · 只读</Tag>}
        </div>
        <div className={styles.headerActions}>
          {!version && (
            <Button icon={<DownloadIcon />} onClick={() => void api.downloadFile(projectId, path)}>
              下载文件
            </Button>
          )}
          <Button onClick={() => navigate(backHref)}>返回 Files</Button>
          {!version && onChanged && (
            <FileObjectActions
              projectId={projectId}
              path={path}
              canWrite={canWrite}
              onChanged={onChanged}
            />
          )}
        </div>
      </div>
      <AsyncState
        loading={file.loading}
        loadingText="正在加载文件…"
        error={error ? { ...error, message: '无法加载文件。' } : undefined}
        onRetry={file.reload}
      >
        {file.data && (
          <Card className={styles.viewerCard}>
            {file.data.truncated && (
              <Typography.Paragraph type="warning">
                文件过大，只显示开头内容，不能保存。
              </Typography.Paragraph>
            )}
            {readOnly ? (
              <Highlight theme={themes.github} code={content} language={languageForPath(path)}>
                {({ className, style, tokens, getLineProps, getTokenProps }) => (
                  <pre className={`${className} ${styles.codeViewer}`} style={style}>
                    {tokens.map((line, index) => (
                      <div key={index} {...getLineProps({ line })}>
                        {line.map((token, tokenIndex) => (
                          <span key={tokenIndex} {...getTokenProps({ token })} />
                        ))}
                      </div>
                    ))}
                  </pre>
                )}
              </Highlight>
            ) : (
              <textarea
                className={styles.editor}
                readOnly={!canWrite || file.data.truncated}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                aria-label={`编辑 ${path}`}
              />
            )}
            {canWrite && !file.data.truncated && (
              <div className={styles.actions}>
                <Button type="primary" onClick={save} loading={saving}>
                  保存
                </Button>
              </div>
            )}
          </Card>
        )}
      </AsyncState>
    </div>
  )
}
