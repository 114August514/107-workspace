import { PlayCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { ComputePlan, Environment, Project, RunConfiguration } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { AsyncSection } from '../common/AsyncSection'
import { RunConfigurationModal } from './RunConfigurationModal'

interface Props {
  projectId: string
  access: Project | undefined
  defaultConfigurationId: string | null
  onSubmitRun: (configuration: RunConfiguration) => void
  onChanged: () => void
}

export function RunConfigurationPanel({
  projectId,
  access,
  defaultConfigurationId,
  onSubmitRun,
  onChanged,
}: Props) {
  const canManage = can(access, 'run_configuration.manage')
  const canSubmit = can(access, 'run.submit')
  const configurations = useAsync<RunConfiguration[]>(
    () => api.listRunConfigurations(projectId),
    [projectId],
  )
  const plans = useAsync<ComputePlan[]>(() => api.computePlans(), [])
  const environments = useAsync<Environment[]>(
    () => api.environmentsForProject(projectId),
    [projectId],
  )
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<RunConfiguration | null>(null)
  const availableVersionCount = (environments.data ?? []).reduce(
    (count, environment) =>
      count + environment.versions.filter((version) => version.available).length,
    0,
  )

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

  const environmentVersions = Object.fromEntries(
    (environments.data ?? []).flatMap((environment) =>
      environment.versions.map((version) => [version.id, { environment, version }] as const),
    ),
  ) as Record<string, { environment: Environment; version: Environment['versions'][number] }>

  const columns: ColumnsType<RunConfiguration> = [
    {
      title: '名称',
      dataIndex: field<RunConfiguration>('name'),
      render: (name: string, configuration) => (
        <Space wrap size={4}>
          <Typography.Text strong>{name}</Typography.Text>
          {configuration.id === defaultConfigurationId && <Tag color="blue">默认</Tag>}
        </Space>
      ),
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
      title: 'Environment Version',
      key: 'environment',
      render: (_, configuration) => {
        const selected = environmentVersions[configuration.environment_version_id]
        if (!selected) {
          return (
            <Space wrap size={4}>
              <Typography.Text code>{configuration.environment_version_id}</Typography.Text>
              <Tag color="red">当前无 USE 资格或已删除</Tag>
            </Space>
          )
        }
        return (
          <Space wrap size={4}>
            <RouterLink to={`/environment-versions/${selected.version.id}`}>
              {selected.environment.name} · {selected.version.version}
            </RouterLink>
            <Tag color={selected.version.available ? 'green' : 'orange'}>
              {selected.version.available ? '可用' : '当前不可用'}
            </Tag>
          </Space>
        )
      },
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
      {environments.loading ? (
        <Alert type="info" showIcon message="正在读取当前 Project 可用的 Environment Version…" />
      ) : environments.error ? (
        <Alert
          type="error"
          showIcon
          message="无法读取当前 Project 可用的 Environment Version"
          description="请检查网络后重试；运行方案不会自动切换到其他版本。"
        />
      ) : availableVersionCount === 0 ? (
        <Alert
          type="warning"
          showIcon
          message="当前没有可用的 Environment Version"
          description="请确认版本可用状态，或让资产 Owner 为 Project Owner 建立 USE Grant。"
        />
      ) : null}

      {canManage && (
        <Button
          icon={<PlusOutlined />}
          disabled={
            environments.loading || Boolean(environments.error) || availableVersionCount === 0
          }
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
