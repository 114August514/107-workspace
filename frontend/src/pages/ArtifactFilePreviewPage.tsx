import { ArrowLeftIcon, DownloadIcon, FileIcon } from '@primer/octicons-react'
import { Banner, Button, Link, Text } from '@primer/react'
import { Blankslate } from '@primer/react/experimental'
import { useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError, type AsyncErrorView } from '../api/errors'
import type { ArtifactEntry, RunDetail } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { CodeViewer } from '../components/common/CodeViewer'
import styles from '../components/run/run.module.css'
import { formatBytes } from '../utils/format'

const MAX_TEXT_PREVIEW_BYTES = 2 * 1024 * 1024
const MAX_IMAGE_PREVIEW_BYTES = 20 * 1024 * 1024

const LANGUAGE_BY_EXTENSION: Record<string, string> = {
  bash: 'bash',
  css: 'css',
  html: 'markup',
  js: 'javascript',
  json: 'json',
  jsonl: 'json',
  jsx: 'jsx',
  md: 'markdown',
  py: 'python',
  sh: 'bash',
  sql: 'sql',
  ts: 'typescript',
  tsx: 'tsx',
  xml: 'markup',
  yaml: 'yaml',
  yml: 'yaml',
}

const TEXT_EXTENSION: Record<string, true> = {
  bash: true,
  cfg: true,
  conf: true,
  css: true,
  csv: true,
  env: true,
  err: true,
  htm: true,
  html: true,
  ini: true,
  js: true,
  json: true,
  jsonl: true,
  jsx: true,
  log: true,
  md: true,
  out: true,
  py: true,
  sh: true,
  slurm: true,
  sql: true,
  toml: true,
  ts: true,
  tsv: true,
  tsx: true,
  txt: true,
  xml: true,
  yaml: true,
  yml: true,
  zsh: true,
}

const IMAGE_EXTENSION: Record<string, true> = {
  avif: true,
  gif: true,
  jpeg: true,
  jpg: true,
  png: true,
  svg: true,
  webp: true,
}

const IMAGE_MIME_BY_EXTENSION: Record<string, string> = {
  avif: 'image/avif',
  gif: 'image/gif',
  jpeg: 'image/jpeg',
  jpg: 'image/jpeg',
  png: 'image/png',
  svg: 'image/svg+xml',
  webp: 'image/webp',
}

const BINARY_EXTENSION: Record<string, true> = {
  '7z': true,
  a: true,
  avi: true,
  bin: true,
  bz2: true,
  ckpt: true,
  docx: true,
  exe: true,
  gz: true,
  h5: true,
  hdf5: true,
  mp3: true,
  mp4: true,
  mov: true,
  npy: true,
  npz: true,
  o: true,
  onnx: true,
  parquet: true,
  pdf: true,
  pptx: true,
  pt: true,
  pth: true,
  so: true,
  tar: true,
  wasm: true,
  wav: true,
  xlsx: true,
  xz: true,
  zip: true,
}

type ArtifactPreview =
  | { kind: 'text'; content: string; language?: string }
  | { kind: 'image'; blob: Blob }
  | { kind: 'unavailable'; reason: string }

function extension(path: string): string {
  const name = path.split('/').at(-1) ?? path
  const dot = name.lastIndexOf('.')
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ''
}

async function loadPreview(artifactId: string, entry: ArtifactEntry): Promise<ArtifactPreview> {
  const fileExtension = extension(entry.path)

  if (IMAGE_EXTENSION[fileExtension]) {
    if (entry.size > MAX_IMAGE_PREVIEW_BYTES) {
      return { kind: 'unavailable', reason: '图片超过 20 MiB，请下载后查看。' }
    }
    const blob = await api.readArtifactFile(artifactId, entry.path)
    return {
      kind: 'image',
      blob: blob.slice(0, blob.size, IMAGE_MIME_BY_EXTENSION[fileExtension]),
    }
  }

  if (BINARY_EXTENSION[fileExtension]) {
    return { kind: 'unavailable', reason: '这是二进制文件，请下载后使用对应工具打开。' }
  }
  if (entry.size > MAX_TEXT_PREVIEW_BYTES) {
    return { kind: 'unavailable', reason: '文件超过 2 MiB，请下载后查看。' }
  }

  const blob = await api.readArtifactFile(artifactId, entry.path)
  const bytes = new Uint8Array(await blob.arrayBuffer())
  if (!TEXT_EXTENSION[fileExtension] && bytes.includes(0)) {
    return { kind: 'unavailable', reason: '未识别到可安全显示的文本内容，请下载后查看。' }
  }

  try {
    const content = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
    return { kind: 'text', content, language: LANGUAGE_BY_EXTENSION[fileExtension] }
  } catch {
    return { kind: 'unavailable', reason: '文件不是有效的 UTF-8 文本，请下载后查看。' }
  }
}

function contextualError(error: Error | undefined, message: string): AsyncErrorView | undefined {
  const view = toAsyncError(error)
  return view ? { ...view, message } : undefined
}

function ImagePreview({ blob, name }: { blob: Blob; name: string }) {
  const [url, setUrl] = useState<string>()

  useEffect(() => {
    const nextUrl = URL.createObjectURL(blob)
    setUrl(nextUrl)
    return () => URL.revokeObjectURL(nextUrl)
  }, [blob])

  return url ? <img className={styles.artifactPreviewImage} src={url} alt={`${name} 预览`} /> : null
}

export function ArtifactFilePreviewPage() {
  const { projectId = '', runId = '', artifactId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const path = searchParams.get('path') ?? ''
  const detail = useAsync<RunDetail>(() => api.getRun(runId), [runId])
  const artifact = detail.data?.artifacts.find((candidate) => candidate.id === artifactId)
  const entries = useAsync<ArtifactEntry[]>(
    async () => (artifact ? api.listArtifactFiles(artifact.id) : []),
    [artifact?.id],
  )
  const entry = entries.data?.find((candidate) => candidate.path === path)
  const preview = useAsync<ArtifactPreview | undefined>(
    async () => (artifact && entry ? loadPreview(artifact.id, entry) : undefined),
    [artifact?.id, entry?.path, entry?.size],
  )
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<Error>()

  useEffect(() => {
    const run = detail.data?.run
    if (!run || run.project_id === projectId) return
    navigate(
      `/projects/${run.project_id}/runs/${run.id}/artifacts/${artifactId}/file?path=${encodeURIComponent(path)}`,
      { replace: true },
    )
  }, [artifactId, detail.data?.run, navigate, path, projectId])

  const download = async () => {
    if (!artifact || !entry) return
    setDownloading(true)
    setDownloadError(undefined)
    try {
      await api.downloadArtifactFile(artifact.id, entry.path)
    } catch (error) {
      setDownloadError(error as Error)
    } finally {
      setDownloading(false)
    }
  }

  const fileName = path.split('/').at(-1) ?? path
  const backPath = `/projects/${projectId}/runs/${runId}#run-artifacts`
  const loading = detail.loading || (artifact !== undefined && entries.loading)
  const error = contextualError(detail.error ?? entries.error, '无法加载这个运行产物文件。')

  return (
    <AsyncState loading={loading} loadingText="正在加载运行产物文件…" error={error}>
      {detail.data && !artifact ? (
        <Banner variant="critical">
          <Banner.Title>找不到这个运行产物。</Banner.Title>
        </Banner>
      ) : null}
      {artifact && !path ? (
        <Banner variant="critical">
          <Banner.Title>没有指定要预览的文件。</Banner.Title>
        </Banner>
      ) : null}
      {artifact && path && entries.data && !entry ? (
        <Banner variant="critical">
          <Banner.Title>找不到这个运行产物文件。</Banner.Title>
        </Banner>
      ) : null}
      {artifact && entry ? (
        <div className={styles.page}>
          <div className={`${styles.runSurface} ${styles.artifactPreviewSurface}`}>
            <Link as={RouterLink} to={backPath} className={styles.backLink}>
              <ArrowLeftIcon size={16} aria-hidden />
              返回运行产物
            </Link>
            <header className={styles.artifactPreviewHeader}>
              <div className={styles.titleGroup}>
                <h1 className={styles.pageTitle}>{fileName}</h1>
                <p className={styles.artifactPreviewPath}>
                  {artifact.name} / <code className={styles.inlineCode}>{path}</code>
                </p>
                <Text size="small" className={styles.muted}>
                  {formatBytes(entry.size)}
                </Text>
              </div>
              <Button
                leadingVisual={DownloadIcon}
                loading={downloading}
                onClick={() => void download()}
              >
                下载
              </Button>
            </header>
            {downloadError ? (
              <Banner variant="critical">
                <Banner.Title>无法下载这个文件。</Banner.Title>
                <Banner.Description>
                  {toAsyncError(downloadError)?.problems?.[0]}
                </Banner.Description>
              </Banner>
            ) : null}
            <section className={styles.artifactPreviewBody} aria-label="文件预览">
              <AsyncState
                loading={preview.loading}
                loadingText="正在读取文件内容…"
                error={contextualError(preview.error, '无法读取这个文件。')}
              >
                {preview.data?.kind === 'text' ? (
                  <CodeViewer
                    content={preview.data.content}
                    language={preview.data.language}
                    ariaLabel={`${fileName} 内容`}
                  />
                ) : null}
                {preview.data?.kind === 'image' ? (
                  <ImagePreview blob={preview.data.blob} name={fileName} />
                ) : null}
                {preview.data?.kind === 'unavailable' ? (
                  <Blankslate narrow>
                    <Blankslate.Visual>
                      <FileIcon size={24} />
                    </Blankslate.Visual>
                    <Blankslate.Heading>无法在浏览器中预览这个文件</Blankslate.Heading>
                    <Blankslate.Description>{preview.data.reason}</Blankslate.Description>
                  </Blankslate>
                ) : null}
              </AsyncState>
            </section>
          </div>
        </div>
      ) : null}
    </AsyncState>
  )
}
