import { PlayCircleOutlined, PlusOutlined, WarningOutlined } from '@ant-design/icons'
import { Button, Popconfirm, Space, Table, Tag, Tooltip, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { ComputePlan, Environment, RunConfiguration, Workspace } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { AsyncSection } from '../common/AsyncSection'
import { RunConfigurationModal } from './RunConfigurationModal'
import { describeMissing, findMissingReferences } from './unresolved'

interface Props {
  projectId: string
  workspace: Workspace | undefined
  defaultConfigurationId: string | null
  onSubmitRun: (configuration: RunConfiguration) => void
  onChanged: () => void
}

export function RunConfigurationPanel({
  projectId,
  workspace,
  defaultConfigurationId,
  onSubmitRun,
  onChanged,
}: Props) {
  const canManage = can(workspace, 'run_configuration.manage')
  const canSubmit = can(workspace, 'run.submit')
  const configurations = useAsync<RunConfiguration[]>(
    () => api.listRunConfigurations(projectId),
    [projectId],
  )
  const plans = useAsync<ComputePlan[]>(() => api.computePlans(), [])
  // 用来判断哪些引用在当前空间解析不了。Fork 过来的方案常常缺东西——
  // 等用户点了提交才告诉他，就太晚了。
  const secretNames = useAsync<string[]>(
    async () => (workspace ? api.listSecretNames(workspace.id) : []),
    [workspace?.id],
  )
  const variables = useAsync(
    async () => (workspace ? api.listVariables(workspace.id) : []),
    [workspace?.id],
  )
  const available = {
    secrets: secretNames.data ?? [],
    variables: (variables.data ?? []).map((v) => v.name),
  }
  const environments = useAsync<Environment[]>(() => api.environments(), [])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<RunConfiguration | null>(null)

  const remove = async (configuration: RunConfiguration) => {
    try {
      await api.deleteRunConfiguration(configuration.id)
      message.success('已删除运行方案')
      configurations.reload()
      onChanged()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<RunConfiguration> = [
    {
      title: '名称',
      dataIndex: field<RunConfiguration>('name'),
      render: (name: string, configuration) => {
        const missing = findMissingReferences(configuration.environment_variables, available)
        return (
          <Space wrap size={4}>
            <Typography.Text strong>{name}</Typography.Text>
            {configuration.id === defaultConfigurationId && <Tag color="blue">默认</Tag>}
            {missing.length > 0 && (
              <Tooltip title={`${describeMissing(missing)}，在这个 Workspace 里不存在`}>
                <Tag color="warning" icon={<WarningOutlined />}>
                  未解析
                </Tag>
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    {
      title: '执行命令',
      dataIndex: field<RunConfiguration>('command'),
      render: (command: string) => <Typography.Text code>{command}</Typography.Text>,
    },
    {
      title: '工作目录',
      dataIndex: field<RunConfiguration>('working_directory'),
      width: 110,
    },
    {
      title: '环境变量',
      key: 'env',
      width: 120,
      render: (_, configuration) => Object.keys(configuration.environment_variables).length,
    },
    {
      title: '产物规则',
      key: 'rules',
      width: 100,
      render: (_, configuration) => configuration.artifact_rules.length,
    },
    {
      title: '操作',
      key: 'actions',
      width: 210,
      render: (_, configuration) => (
        <Space size={4}>
          {canSubmit && (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => onSubmitRun(configuration)}
            >
              提交 Run
            </Button>
          )}
          {canManage && (
            <Button
              type="link"
              size="small"
              onClick={() => {
                setEditing(configuration)
                setModalOpen(true)
              }}
            >
              编辑
            </Button>
          )}
          {canManage && (
            <Popconfirm
              title={`删除「${configuration.name}」？`}
              description="已经创建的 Run 不受影响，它们按各自的运行快照执行。"
              okText="删除"
              cancelText="取消"
              onConfirm={() => remove(configuration)}
            >
              <Button type="link" size="small" danger>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {canManage && (
        <Button
          icon={<PlusOutlined />}
          onClick={() => {
            setEditing(null)
            setModalOpen(true)
          }}
        >
          新建运行方案
        </Button>
      )}

      <AsyncSection
        loading={configurations.loading}
        error={configurations.error}
        empty={(configurations.data ?? []).length === 0}
        emptyText="还没有运行方案。新建一个，就可以提交 Run 了。"
      >
        <Table
          rowKey="id"
          size="small"
          dataSource={configurations.data ?? []}
          columns={columns}
          pagination={false}
        />
      </AsyncSection>

      <RunConfigurationModal
        open={modalOpen}
        projectId={projectId}
        plans={plans.data ?? []}
        environments={environments.data ?? []}
        editing={editing}
        onClose={() => setModalOpen(false)}
        onSaved={() => {
          configurations.reload()
          onChanged()
        }}
      />
    </Space>
  )
}
