import {
  Alert,
  Button,
  Drawer,
  Input,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type {
  ChangeKind,
  Project,
  ProjectVersion,
  ProjectVersionPage,
  WorkingChange,
  WorkingChangeDetail,
} from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { formatBytes, formatTime } from '../../utils/format'
import { AsyncSection } from '../common/AsyncSection'
import { ForkModal } from './ForkModal'
import { tablePagination } from '../../utils/pagination'

const CHANGE_LABEL: Record<ChangeKind, { text: string; color: string }> = {
  added: { text: '新增', color: 'green' },
  modified: { text: '修改', color: 'blue' },
  removed: { text: '删除', color: 'red' },
}
type VersionPanelSection = 'all' | 'changes' | 'versions'

interface Props {
  section?: VersionPanelSection
  projectId: string
  projectName: string
  access: Project | undefined
  refreshToken: number
  onVersionSaved: () => void
}

/**
 * 版本历史与未保存变更。
 *
 * Project Version 是不可变快照，恢复历史版本改的是工作区，不会动那个版本。
 */
export function VersionPanel({
  section = 'all',
  projectId,
  projectName,
  access,
  refreshToken,
  onVersionSaved,
}: Props) {
  const showChanges = section !== 'versions'
  const showVersions = section !== 'changes'
  const navigate = useNavigate()
  const [forking, setForking] = useState<ProjectVersion | null>(null)
  const [inspecting, setInspecting] = useState<WorkingChange | null>(null)
  const canWrite = can(access, 'project.content.write')
  const [page, setPage] = useState(1)
  const versions = useAsync<ProjectVersionPage>(
    () => api.listVersions(projectId, { page }),
    [projectId, refreshToken, page],
  )
  const changes = useAsync<WorkingChange[]>(
    () => api.workingChanges(projectId),
    [projectId, refreshToken],
  )
  const [message_, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  const pending = changes.data ?? []

  const save = async () => {
    setSaving(true)
    try {
      const version = await api.saveVersion(projectId, message_)
      message.success(`已保存 ${version.label}`)
      setMessage('')
      versions.reload()
      changes.reload()
      onVersionSaved()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const restore = async (version: ProjectVersion) => {
    try {
      await api.restoreVersion(version.id)
      message.success(`工作区已恢复到 ${version.label}`)
      changes.reload()
      onVersionSaved()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<ProjectVersion> = [
    {
      title: '版本',
      dataIndex: field<ProjectVersion>('label'),
      width: 80,
      render: (label: string) => <Tag color="geekblue">{label}</Tag>,
    },
    { title: '说明', dataIndex: field<ProjectVersion>('message') },
    { title: '文件数', dataIndex: field<ProjectVersion>('file_count'), width: 90 },
    {
      title: '总大小',
      dataIndex: field<ProjectVersion>('total_size'),
      width: 100,
      render: formatBytes,
    },
    {
      title: '保存时间',
      dataIndex: field<ProjectVersion>('created_at'),
      width: 180,
      render: formatTime,
    },
    {
      title: '操作',
      width: 260,
      key: 'actions',
      render: (_, version) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/projects/${projectId}/files/versions/${version.id}`)}
          >
            查看详情
          </Button>
          {canWrite && (
            <Popconfirm
              title={`把工作区恢复到 ${version.label}？`}
              description="当前未保存的修改会被覆盖。历史版本本身不受影响。"
              okText="恢复"
              cancelText="取消"
              onConfirm={() => restore(version)}
            >
              <Button type="link" size="small">
                恢复到此版本
              </Button>
            </Popconfirm>
          )}
          {/*
            派生只需要能看见这个版本，不需要对**当前**空间有写权限——
            写权限是目标空间的事，由后端和弹窗里的空间列表一起把关。
            所以这里不看 canWrite，否则只有查看能力的用户就没法把可读内容 Fork
            到自己的空间，而那正是 Fork 最主要的用法。
          */}
          <Button type="link" size="small" onClick={() => setForking(version)}>
            派生
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {showChanges && (
        <>
          <AsyncSection loading={changes.loading} error={changes.error}>
            {pending.length === 0 ? (
              <Alert type="success" showIcon message="Working State 与最近保存的 Version 一致" />
            ) : (
              <Alert
                type="info"
                showIcon
                message={`Working State 有 ${pending.length} 个文件变更`}
                description={
                  <Space direction="vertical" size={4} style={{ width: '100%', marginTop: 8 }}>
                    <Typography.Text type="secondary">
                      检查这些变更后，可将整个 Working State 保存为新的 Project Version。
                    </Typography.Text>
                    {pending.map((change) => (
                      <Button
                        key={change.path}
                        type="link"
                        size="small"
                        style={{ display: 'flex', justifyContent: 'flex-start', padding: 0 }}
                        onClick={() => setInspecting(change)}
                      >
                        <Tag color={CHANGE_LABEL[change.change].color}>
                          {CHANGE_LABEL[change.change].text}
                        </Tag>
                        {change.path}
                      </Button>
                    ))}
                  </Space>
                }
              />
            )}
          </AsyncSection>

          {canWrite && (
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="这次改了什么"
                value={message_}
                onChange={(event) => setMessage(event.target.value)}
                onPressEnter={save}
              />
              <Button
                type="primary"
                onClick={save}
                loading={saving}
                disabled={pending.length === 0}
              >
                保存 Project Version
              </Button>
            </Space.Compact>
          )}

          <Typography.Text type="secondary">
            Run 只能从确定的 Project Version 发起。保存版本之后，这份内容就固定下来了。
          </Typography.Text>
        </>
      )}

      {showVersions && (
        <AsyncSection
          loading={versions.loading}
          error={versions.error}
          empty={versions.data?.total === 0}
          emptyText="还没有保存过版本"
        >
          <Table
            rowKey="id"
            size="small"
            dataSource={versions.data?.items ?? []}
            columns={columns}
            pagination={tablePagination(versions.data, setPage)}
          />
        </AsyncSection>
      )}

      {showVersions && (
        <ForkModal
          open={forking !== null}
          version={forking}
          sourceProjectName={projectName}
          onClose={() => setForking(null)}
          onForked={(project) => navigate(`/projects/${project.id}`)}
        />
      )}
      {showChanges && (
        <ChangeDetailDrawer
          projectId={projectId}
          change={inspecting}
          changes={pending}
          canWrite={canWrite}
          onSelect={setInspecting}
          onClose={() => setInspecting(null)}
          onDiscarded={() => {
            changes.reload()
            onVersionSaved()
          }}
        />
      )}
    </Space>
  )
}

/** 单个未保存变更的内容级详情：基线与工作区两侧并排，可直接放弃。 */
function ChangeDetailDrawer({
  projectId,
  change,
  changes,
  canWrite,
  onSelect,
  onClose,
  onDiscarded,
}: {
  projectId: string
  change: WorkingChange | null
  changes: WorkingChange[]
  canWrite: boolean
  onSelect: (change: WorkingChange) => void
  onClose: () => void
  onDiscarded: () => void
}) {
  const [detail, setDetail] = useState<WorkingChangeDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [retryToken, setRetryToken] = useState(0)
  const [discarding, setDiscarding] = useState(false)

  useEffect(() => {
    if (!change) return
    let cancelled = false
    setLoading(true)
    setDetail(null)
    setLoadError(null)
    api
      .workingChangeDetail(projectId, change.path)
      .then((result) => {
        if (!cancelled) setDetail(result)
      })
      .catch((error) => {
        if (!cancelled) setLoadError((error as Error).message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, change, retryToken])

  const discard = async () => {
    if (!change) return
    setDiscarding(true)
    try {
      await api.discardChanges(projectId, [change.path])
      message.success(`已放弃 ${change.path} 的未保存变更`)
      onClose()
      onDiscarded()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setDiscarding(false)
    }
  }

  return (
    <Drawer
      open={change !== null}
      title={change?.path}
      width={860}
      onClose={onClose}
      extra={
        canWrite &&
        change && (
          <Popconfirm
            title={`放弃 ${change.path} 的未保存变更？`}
            description="工作区会恢复到最近保存版本的内容。历史版本不受影响，但这次修改无法找回。"
            okText="放弃变更"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => void discard()}
          >
            <Button danger loading={discarding}>
              放弃此变更
            </Button>
          </Popconfirm>
        )
      }
    >
      {changes.length > 0 && (
        <Space direction="vertical" size={4} style={{ width: '100%', marginBottom: 16 }}>
          <Typography.Text strong>更改 ({changes.length})</Typography.Text>
          {changes.map((item) => (
            <Button key={item.path} type={item.path === change?.path ? 'primary' : 'text'} block onClick={() => onSelect(item)} style={{ textAlign: 'left' }}>
              <Tag color={CHANGE_LABEL[item.change].color}>{item.change === 'modified' ? 'M' : item.change === 'added' ? 'A' : 'D'}</Tag>{item.path}
            </Button>
          ))}
        </Space>
      )}
      {loading ? (
        <Spin />
      ) : loadError ? (
        <Alert
          type="error"
          showIcon
          message="无法加载变更详情"
          description={
            <Space direction="vertical" size="small">
              <Typography.Text>{loadError}</Typography.Text>
              <Button onClick={() => setRetryToken((current) => current + 1)}>重试</Button>
            </Space>
          }
        />
      ) : detail ? (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap size={[8, 8]}>
            <Tag color={CHANGE_LABEL[detail.change].color}>{CHANGE_LABEL[detail.change].text}</Tag>
            {detail.previous?.truncated && (
              <Typography.Text type="secondary">基线内容过长，仅显示前 256 KB</Typography.Text>
            )}
            {detail.current?.truncated && (
              <Typography.Text type="secondary">工作区内容过长，仅显示前 256 KB</Typography.Text>
            )}
          </Space>
          <DiffView
            previous={detail.previous?.content ?? null}
            current={detail.current?.content ?? null}
            previousEmpty="此路径在基线版本中不存在"
            currentEmpty="文件已被删除"
          />
        </Space>
      ) : null}
    </Drawer>
  )
}

function DiffView({ previous, current, previousEmpty, currentEmpty }: { previous: string | null; current: string | null; previousEmpty: string; currentEmpty: string }) {
  if (previous === null || current === null) {
    return <Typography.Text type="secondary">{previous === null ? previousEmpty : currentEmpty}</Typography.Text>
  }
  const oldLines = previous.split('\n')
  const newLines = current.split('\n')
  const rows: Array<{ kind: 'same' | 'remove' | 'add'; old: number | ''; next: number | ''; text: string }> = []
  let old = 0
  let next = 0
  while (old < oldLines.length || next < newLines.length) {
    if (oldLines[old] === newLines[next]) {
      rows.push({ kind: 'same', old: old + 1, next: next + 1, text: oldLines[old] ?? '' }); old++; next++
    } else if (old < oldLines.length && (next >= newLines.length || !newLines.slice(next + 1).includes(oldLines[old]!))) {
      rows.push({ kind: 'remove', old: old + 1, next: '', text: oldLines[old]! }); old++
    } else {
      rows.push({ kind: 'add', old: '', next: next + 1, text: newLines[next] ?? '' }); next++
    }
  }
  return <div style={{ overflowX: 'auto', border: '1px solid #d0d7de', borderRadius: 6, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12 }}>
    {rows.map((row, index) => <div key={`${row.kind}-${index}`} style={{ display: 'grid', gridTemplateColumns: '48px 48px 1fr', whiteSpace: 'pre', background: row.kind === 'remove' ? '#ffebe9' : row.kind === 'add' ? '#dafbe1' : undefined }}>
      <span style={{ padding: '2px 8px', textAlign: 'right', color: '#6e7781', borderRight: '1px solid #d0d7de' }}>{row.old}</span>
      <span style={{ padding: '2px 8px', textAlign: 'right', color: '#6e7781', borderRight: '1px solid #d0d7de' }}>{row.next}</span>
      <span style={{ padding: '2px 12px' }}><b>{row.kind === 'remove' ? '−' : row.kind === 'add' ? '+' : ' '}</b> {row.text}</span>
    </div>)}
  </div>
}
