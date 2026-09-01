import {
  ChevronRightIcon,
  DownloadIcon,
  FileDirectoryIcon,
  FileIcon,
  PackageIcon,
} from '@primer/octicons-react'
import { Banner, IconButton, Label, Link, Text } from '@primer/react'
import { Blankslate } from '@primer/react/experimental'
import { useMemo, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import type { Artifact, ArtifactEntry } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { formatBytes, formatTime } from '../../utils/format'
import { AsyncState } from '../common/AsyncState'
import styles from './run.module.css'

interface ArtifactFileNode {
  kind: 'file'
  name: string
  path: string
  size: number
}

interface ArtifactDirectoryNode {
  kind: 'directory'
  name: string
  path: string
  children: ArtifactTreeNode[]
}

type ArtifactTreeNode = ArtifactFileNode | ArtifactDirectoryNode

function artifactTree(entries: ArtifactEntry[]): ArtifactTreeNode[] {
  const roots: ArtifactTreeNode[] = []
  const directories = new Map<string, ArtifactDirectoryNode>()

  for (const entry of [...entries].sort((left, right) => left.path.localeCompare(right.path))) {
    const parts = entry.path.split('/').filter(Boolean)
    if (parts.length === 0) continue

    let children = roots
    for (const [index, name] of parts.slice(0, -1).entries()) {
      const path = parts.slice(0, index + 1).join('/')
      let directory = directories.get(path)
      if (directory === undefined) {
        directory = {
          kind: 'directory',
          name,
          path,
          children: [],
        }
        directories.set(path, directory)
        children.push(directory)
      }
      children = directory.children
    }

    children.push({
      kind: 'file',
      name: parts.at(-1) ?? entry.path,
      path: entry.path,
      size: entry.size,
    })
  }

  const sort = (nodes: ArtifactTreeNode[]) => {
    nodes.sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === 'directory' ? -1 : 1
      return left.name.localeCompare(right.name)
    })
    for (const node of nodes) {
      if (node.kind === 'directory') sort(node.children)
    }
  }
  sort(roots)
  return roots
}

function ArtifactTreeItem({
  node,
  downloading,
  onDownload,
  previewBase,
}: {
  node: ArtifactTreeNode
  downloading: string | null
  onDownload: (path: string) => void
  previewBase: string
}) {
  const [open, setOpen] = useState(false)

  if (node.kind === 'directory') {
    return (
      <li className={styles.artifactTreeItem}>
        <details
          className={styles.artifactDirectory}
          open={open}
          onToggle={(event) => setOpen(event.currentTarget.open)}
        >
          <summary title={node.path}>
            <ChevronRightIcon className={styles.artifactChevron} size={16} aria-hidden />
            <FileDirectoryIcon size={16} aria-hidden />
            <span className={styles.artifactTreeName}>{node.name}/</span>
          </summary>
          <ul className={styles.artifactTreeChildren}>
            {node.children.map((child) => (
              <ArtifactTreeItem
                key={child.path}
                node={child}
                downloading={downloading}
                onDownload={onDownload}
                previewBase={previewBase}
              />
            ))}
          </ul>
        </details>
      </li>
    )
  }

  return (
    <li className={styles.artifactTreeItem}>
      <div className={styles.artifactFileRow} title={node.path}>
        <FileIcon size={16} aria-hidden />
        <Link
          as={RouterLink}
          to={`${previewBase}?path=${encodeURIComponent(node.path)}`}
          className={styles.artifactFileLink}
        >
          {node.name}
        </Link>
        <span className={styles.artifactFileSize}>{formatBytes(node.size)}</span>
        <IconButton
          icon={DownloadIcon}
          size="small"
          aria-label={`下载 ${node.path}`}
          loading={downloading === node.path}
          disabled={downloading !== null}
          onClick={() => onDownload(node.path)}
        />
      </div>
    </li>
  )
}

function ArtifactFiles({
  artifact,
  projectId,
  runId,
}: {
  artifact: Artifact
  projectId: string
  runId: string
}) {
  const entries = useAsync<ArtifactEntry[]>(() => api.listArtifactFiles(artifact.id), [artifact.id])
  const tree = useMemo(() => artifactTree(entries.data ?? []), [entries.data])
  const previewBase = `/projects/${projectId}/runs/${runId}/artifacts/${artifact.id}/file`
  const [downloading, setDownloading] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<Error | undefined>()

  const download = async (path: string) => {
    setDownloading(path)
    setDownloadError(undefined)
    try {
      await api.downloadArtifactFile(artifact.id, path)
    } catch (error) {
      setDownloadError(error as Error)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <AsyncState
      loading={entries.loading}
      loadingText="正在读取运行产物文件…"
      error={
        entries.error
          ? { ...toAsyncError(entries.error), message: '无法读取这个运行产物。' }
          : undefined
      }
      onRetry={entries.reload}
      empty={tree.length === 0}
      emptyText="这个运行产物没有文件。"
    >
      {downloadError ? (
        <div className={styles.inlineBanner}>
          <Banner variant="critical">
            <Banner.Title>无法下载这个文件。</Banner.Title>
            <Banner.Description>{toAsyncError(downloadError)?.problems?.[0]}</Banner.Description>
          </Banner>
        </div>
      ) : null}
      <div className={styles.artifactTreeHeader} aria-hidden>
        <span />
        <span>名称</span>
        <span>大小</span>
        <span>操作</span>
      </div>
      <ul className={styles.artifactTree} aria-label={`${artifact.name} 文件`}>
        {tree.map((node) => (
          <ArtifactTreeItem
            key={node.path}
            node={node}
            downloading={downloading}
            onDownload={(path) => void download(path)}
            previewBase={previewBase}
          />
        ))}
      </ul>
    </AsyncState>
  )
}

function ArtifactGroup({
  artifact,
  projectId,
  runId,
}: {
  artifact: Artifact
  projectId: string
  runId: string
}) {
  const [open, setOpen] = useState(true)

  return (
    <details
      className={styles.artifactGroup}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <ChevronRightIcon className={styles.artifactChevron} size={16} aria-hidden />
        <div className={styles.artifactGroupHeading}>
          <span className={styles.artifactGroupTitle}>
            <strong>{artifact.name}</strong>
            {artifact.status !== 'available' ? <Label variant="attention">内容已清理</Label> : null}
          </span>
          <span className={styles.artifactGroupMeta}>
            <span>
              收集自 <code className={styles.inlineCode}>{artifact.source_path}</code>
            </span>
            <span>收集于 {formatTime(artifact.created_at)}</span>
          </span>
        </div>
      </summary>
      <div className={styles.artifactGroupBody}>
        {artifact.description ? (
          <Text as="p" size="small" className={styles.artifactDescription}>
            {artifact.description}
          </Text>
        ) : null}
        {artifact.status === 'available' ? (
          <ArtifactFiles artifact={artifact} projectId={projectId} runId={runId} />
        ) : (
          <div className={styles.emptyInline}>内容已清理；运行产物记录仍保留在 Run 历史中。</div>
        )}
      </div>
    </details>
  )
}

export function ArtifactPanel({
  artifacts,
  projectId,
  runId,
}: {
  artifacts: Artifact[]
  projectId: string
  runId: string
}) {
  if (artifacts.length === 0) {
    return (
      <Blankslate narrow>
        <Blankslate.Visual>
          <PackageIcon size={24} />
        </Blankslate.Visual>
        <Blankslate.Heading>这个 Run 没有产生运行产物。</Blankslate.Heading>
      </Blankslate>
    )
  }

  return (
    <div className={styles.artifactGroups}>
      {artifacts.map((artifact) => (
        <ArtifactGroup key={artifact.id} artifact={artifact} projectId={projectId} runId={runId} />
      ))}
    </div>
  )
}
