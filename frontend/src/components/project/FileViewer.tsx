import { EditorView } from '@codemirror/view'
import { DownloadIcon, HomeIcon } from '@primer/octicons-react'
import { Button, Card, Tag, Typography } from 'antd'
import { Highlight, themes } from 'prism-react-renderer'
import { langs } from '@uiw/codemirror-extensions-langs'
import CodeMirror from '@uiw/react-codemirror'
import { useEffect, useMemo, useState } from 'react'
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
  rootHref?: string
  version?: ProjectVersionDetail
  onChanged?: () => void
  workingHref?: string
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
const editorLanguages = {
  js: langs.js, jsx: langs.jsx, ts: langs.ts, tsx: langs.tsx,
  json: langs.json, md: langs.markdown, py: langs.python, yaml: langs.yaml, yml: langs.yaml,
  cpp: langs.cpp, cc: langs.cpp, hpp: langs.cpp, java: langs.java, go: langs.go, sh: langs.sh, bash: langs.bash,
}
function editorLanguage(path: string) {
  const extension = path.split('.').at(-1)?.toLowerCase()
  const factory = editorLanguages[extension as keyof typeof editorLanguages]
  return factory ? [factory()] : []
}
export function FileViewer({
  projectId,
  access,
  path,
  backHref,
  rootHref = backHref,
  version,
  onChanged,
  workingHref,
}: Props) {
  const navigate = useNavigate()
  const editorExtensions = useMemo(() => editorLanguage(path), [path])
  const readOnly = version !== undefined
  const canWrite = !readOnly && can(access, 'project.content.write')
  const fileName = path.split('/').at(-1) ?? path
  const directorySegments = path.split('/').slice(0, -1)
  const directoryHref = (segments: string[]) =>
    segments.length === 0
      ? rootHref
      : `${rootHref}/tree/${segments.map(encodeURIComponent).join('/')}`
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
        <Link to={rootHref} aria-label="返回 Project 文件根目录">
          <HomeIcon size={16} />
        </Link>
        {directorySegments.map((segment, index) => {
          const segments = directorySegments.slice(0, index + 1)
          return (
            <span key={segments.join('/')}>
              <span aria-hidden> / </span>
              <Link to={directoryHref(segments)}>{segment}</Link>
            </span>
          )
        })}
        <span>
          <span aria-hidden> / </span>
          {fileName}
        </span>
      </nav>
      <div className={styles.header}>
        <div>
          <Typography.Title level={3}>{fileName}</Typography.Title>
          {version && <Tag color="blue">{version.label} · 只读</Tag>}
        </div>
        <div className={styles.headerActions}>
          {version && workingHref && (
            <Button onClick={() => navigate(workingHref)}>编辑 Working State</Button>
          )}
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
              <CodeMirror
                className={styles.editor}
                value={content}
                onChange={setContent}
                height="32rem"
                readOnly={!canWrite || file.data.truncated}
                extensions={[...editorExtensions, EditorView.contentAttributes.of({ 'aria-label': `编辑 ${path}` })]}
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
