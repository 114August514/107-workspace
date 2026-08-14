import { Descriptions, Space, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'

import type { RunSnapshot } from '../../api/types'
import { describeComputeRequest, formatTime } from '../../utils/format'

/**
 * 复现信息：这次 Run 到底按什么配置跑的。
 *
 * Run Snapshot 创建后不可修改。后来改运行方案、换环境、调整权益，
 * 都不会改变这里显示的内容。
 */
export function RunSnapshotCard({ snapshot }: { snapshot: RunSnapshot }) {
  const scheduler = snapshot.scheduler
  const secrets = Object.entries(snapshot.secret_references)
  const variables = Object.entries(snapshot.environment_variables)

  return (
    <Descriptions
      size="small"
      column={1}
      bordered
      items={[
        {
          key: 'version',
          label: 'Project Version',
          children: (
            <Link to={`/versions/${snapshot.project_version_id}`}>
              {snapshot.project_version_id}
            </Link>
          ),
        },
        {
          key: 'command',
          label: '执行命令',
          children: <Typography.Text code>{snapshot.command}</Typography.Text>,
        },
        { key: 'workdir', label: '工作目录', children: snapshot.working_directory },
        {
          key: 'environment',
          label: '运行环境',
          children: (
            <Space direction="vertical" size={2}>
              <Typography.Text code>{snapshot.environment_image}</Typography.Text>
              <Typography.Text type="secondary">{snapshot.environment_version_id}</Typography.Text>
            </Space>
          ),
        },
        {
          key: 'compute',
          label: '算力请求',
          children: describeComputeRequest(snapshot.compute_request),
        },
        {
          key: 'scheduler',
          label: '已解析调度配置',
          children: (
            <Space wrap size={[6, 6]}>
              <Tag>集群 {scheduler.cluster}</Tag>
              <Tag>Account {scheduler.account}</Tag>
              <Tag>Partition {scheduler.partition}</Tag>
              <Tag>QoS {scheduler.qos}</Tag>
            </Space>
          ),
        },
        {
          key: 'env',
          label: '环境变量',
          children:
            variables.length + secrets.length === 0 ? (
              '—'
            ) : (
              <Space direction="vertical" size={4}>
                {variables.map(([name, value]) => (
                  <Typography.Text key={name} code>{`${name}=${value}`}</Typography.Text>
                ))}
                {secrets.map(([name, secret]) => (
                  <Space key={name} size={6}>
                    <Typography.Text code>{name}</Typography.Text>
                    <Tag color="purple">来自 Secret {secret}（值不落快照）</Tag>
                  </Space>
                ))}
              </Space>
            ),
        },
        {
          key: 'inputs',
          label: '输入绑定',
          children:
            snapshot.input_bindings.length === 0 ? (
              '—'
            ) : (
              <Space direction="vertical" size={4}>
                {snapshot.input_bindings.map((binding) => (
                  <Typography.Text key={binding.access_path} code>
                    {`${binding.source_id} → ${binding.access_path}（只读）`}
                  </Typography.Text>
                ))}
              </Space>
            ),
        },
        {
          key: 'rules',
          label: 'Artifact 收集规则',
          children:
            snapshot.artifact_rules.length === 0 ? (
              '—'
            ) : (
              <Space wrap size={[6, 6]}>
                {snapshot.artifact_rules.map((rule) => (
                  <Tag key={rule.path} color={rule.optional ? 'default' : 'blue'}>
                    {rule.path}
                    {rule.optional ? '（可选）' : '（必需）'}
                  </Tag>
                ))}
              </Space>
            ),
        },
        { key: 'created', label: '固定时间', children: formatTime(snapshot.created_at) },
      ]}
    />
  )
}
