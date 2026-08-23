import { Alert, Space, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { api } from '../../api/client'
import type { ComputePlan, Entitlement } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { describeComputeRequest, formatMemory } from '../../utils/format'
import { AsyncSection } from '../common/AsyncSection'

/** 当前用户拥有的算力方案使用资格（Resource Entitlement 属于 User 本人）。 */
export function EntitlementPanel() {
  const entitlements = useAsync<Entitlement[]>(() => api.listEntitlements(), [])
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
        message="这里显示你本人拥有的算力方案使用资格"
        description="Resource Entitlement 属于用户本人，提交 Run 时按发起用户的资格校验；成员身份不会转移算力资格。"
      />
      <AsyncSection
        loading={entitlements.loading || plans.loading}
        error={entitlements.error ?? plans.error}
        empty={(entitlements.data ?? []).length === 0}
        emptyText="你当前没有可用的算力方案资格"
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
