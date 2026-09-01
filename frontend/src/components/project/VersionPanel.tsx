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
          <Button type="link" size="small" onClick={() => navigate(`/versions/${version.id}`)}>
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
              <Alert type="success" showIcon message="工作区没有未保存的变更" />
            ) : (
              <Alert
                type="warning"
                showIcon
                message={`有 ${pending.length} 处未保存的变更`}
                description={
                  <Space wrap size={[8, 8]} style={{ marginTop: 8 }}>
                    {pending.map((change) => (
                      <Button
                        key={change.path}
                        type="link"
                        size="small"
                        onClick={() => setInspecting(change)}
                      >
                        <Tag color={CHANGE_LABEL[change.change].color}>
                          {CHANGE_LABEL[change.change].text} {change.path}
                        </Tag>
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
          canWrite={canWrite}
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
  canWrite,
  onClose,
  onDiscarded,
}: {
  projectId: string
  change: WorkingChange | null
  canWrite: boolean
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
          {/* 二进制内容经 UTF-8 替换解码会出现替代符——照实显示，
              不假装这是精确的文本 diff（后端只存内容摘要）。 */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <DiffSide
              title="最近保存版本"
              content={detail.previous?.content ?? null}
              emptyText="此路径在基线版本中不存在（新增）"
            />
            <DiffSide
              title="当前工作区"
              content={detail.current?.content ?? null}
              emptyText="文件已被删除"
            />
          </div>
        </Space>
      ) : null}
    </Drawer>
  )
}

function DiffSide({
  title,
  content,
  emptyText,
}: {
  title: string
  content: string | null
  emptyText: string
}) {
  return (
    <div style={{ flex: '1 1 320px', minWidth: 0 }}>
      <Typography.Text strong>{title}</Typography.Text>
      {content === null ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
          {emptyText}
        </Typography.Paragraph>
      ) : (
        <pre
          style={{
            marginTop: 8,
            padding: 12,
            background: 'rgba(0, 0, 0, 0.04)',
            borderRadius: 6,
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            fontSize: 12,
            maxHeight: 480,
            overflowY: 'auto',
          }}
        >
          {content}
        </pre>
      )}
    </div>
  )
}
