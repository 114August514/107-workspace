import { Alert, Space, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { api } from '../../api/client'
import type { ComputePlan, Entitlement } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { describeComputeRequest, formatMemory } from '../../utils/format'
import { AsyncSection } from '../common/AsyncSection'

/** 当前 Project 可用的算力方案与并发上限。 */
export function EntitlementPanel({ workspaceId }: { workspaceId: string }) {
  const entitlements = useAsync<Entitlement[]>(
    () => api.listEntitlements(workspaceId),
    [workspaceId],
  )
  const plans = useAsync<ComputePlan[]>(() => api.computePlans(), [])

  const planById = new Map((plans.data ?? []).map((plan) => [plan.id, plan]))

  const columns: ColumnsType<Entitlement> = [
    { title: '算力方案', dataIndex: field<Entitlement>('compute_plan_name'), width: 160 },
    {
      title: '默认资源',
      key: 'default',
      render: (_, entitlement) => {
        const plan = planById.get(entitlement.compute_plan_id)
        if (!plan) return '—'
        return describeComputeRequest({
          nodes: plan.default_nodes,
          cpus: plan.default_cpus,
          memory_mb: plan.default_memory_mb,
          gpus: plan.default_gpus,
          time_limit_minutes: plan.default_time_limit_minutes,
        })
      },
    },
    {
      title: '上限',
      key: 'max',
      render: (_, entitlement) => {
        const plan = planById.get(entitlement.compute_plan_id)
        if (!plan) return '—'
        const parts = [
          `${plan.max_nodes} 节点`,
          `${plan.max_cpus} 核`,
          formatMemory(plan.max_memory_mb),
        ]
        if (plan.max_gpus > 0) parts.push(`${plan.max_gpus} 张 GPU`)
        return <Typography.Text type="secondary">{parts.join(' · ')}</Typography.Text>
      },
    },
    { title: '并发 Run 上限', dataIndex: field<Entitlement>('max_concurrent_runs'), width: 130 },
    {
      title: '有效期',
      dataIndex: field<Entitlement>('expires_at'),
      width: 140,
      render: (value: string | null) => value ?? '长期有效',
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="这里显示当前可用于这些 Project 的算力方案"
        description="算力方案由平台分配；如果当前没有可用方案，相关 Project 就无法提交 Run。"
      />
      <AsyncSection
        loading={entitlements.loading || plans.loading}
        error={entitlements.error ?? plans.error}
        empty={(entitlements.data ?? []).length === 0}
        emptyText="当前没有可用的算力方案"
      >
        <Table
          rowKey="id"
          size="small"
          dataSource={entitlements.data ?? []}
          columns={columns}
          pagination={false}
        />
      </AsyncSection>
    </Space>
  )
}
