import { Alert, Button, Input, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type {
  ChangeKind,
  ProjectVersion,
  ProjectVersionPage,
  WorkingChange,
  Workspace,
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

interface Props {
  projectId: string
  projectName: string
  workspace: Workspace | undefined
  refreshToken: number
  onVersionSaved: () => void
}

/**
 * 版本历史与未保存变更。
 *
 * Project Version 是不可变快照，恢复历史版本改的是工作区，不会动那个版本。
 */
export function VersionPanel({
  projectId,
  projectName,
  workspace,
  refreshToken,
  onVersionSaved,
}: Props) {
  const navigate = useNavigate()
  const [forking, setForking] = useState<ProjectVersion | null>(null)
  const canWrite = can(workspace, 'project.content.write')
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
      width: 190,
      key: 'actions',
      render: (_, version) => (
        <Space size={0}>
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
            所以这里不看 canWrite，否则 Viewer 就没法把别人的东西 Fork
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
                  <Tag key={change.path} color={CHANGE_LABEL[change.change].color}>
                    {CHANGE_LABEL[change.change].text} {change.path}
                  </Tag>
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
          <Button type="primary" onClick={save} loading={saving} disabled={pending.length === 0}>
            保存 Project Version
          </Button>
        </Space.Compact>
      )}

      <Typography.Text type="secondary">
        Run 只能从确定的 Project Version 发起。保存版本之后，这份内容就固定下来了。
      </Typography.Text>

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

      <ForkModal
        open={forking !== null}
        version={forking}
        sourceProjectName={projectName}
        onClose={() => setForking(null)}
        onForked={(project) => navigate(`/projects/${project.id}`)}
      />
    </Space>
  )
}
