import { Table, Typography } from 'antd'
import type { TablePaginationConfig } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'

import type { Run } from '../../api/types'
import { field } from '../../utils/field'
import { formatDuration } from '../../utils/format'
import { Mono, RelativeTime } from '../common/Mono'
import { RunStatusTag } from '../common/RunStatusTag'

const columns: ColumnsType<Run> = [
  // 状态放第一列：扫一列 Run 时先看的就是「成了没有」，
  // 名字是确认用的，不是筛选用的。
  {
    title: '状态',
    dataIndex: field<Run>('status'),
    width: 110,
    render: (_, run) => <RunStatusTag status={run.status} />,
  },
  {
    title: '名称',
    dataIndex: field<Run>('name'),
    // 不加 ellipsis 的话，窄屏下名字会折成三行，把整张表撑得很松
    ellipsis: true,
    render: (name: string, run) => <Link to={`/runs/${run.id}`}>{name}</Link>,
  },
  {
    title: '发起用户',
    dataIndex: field<Run>('initiated_by_username'),
    width: 120,
    render: (username: string | null) => (
      <Typography.Text type={username ? undefined : 'secondary'}>
        {username ?? '未知用户'}
      </Typography.Text>
    ),
  },
  {
    title: '版本',
    dataIndex: field<Run>('project_version_label'),
    width: 80,
    render: (label: string, run) => <Link to={`/versions/${run.project_version_id}`}>{label}</Link>,
  },
  {
    title: '排队',
    dataIndex: field<Run>('queued_seconds'),
    width: 90,
    render: (seconds: number | null) => (
      <Typography.Text type="secondary">{formatDuration(seconds)}</Typography.Text>
    ),
  },
  {
    title: '运行',
    dataIndex: field<Run>('running_seconds'),
    width: 90,
    render: (seconds: number | null) => (
      <Typography.Text type="secondary">{formatDuration(seconds)}</Typography.Text>
    ),
  },
  {
    title: '退出码',
    dataIndex: field<Run>('exit_code'),
    width: 80,
    render: (code: number | null) =>
      code === null ? (
        <Typography.Text type="secondary">—</Typography.Text>
      ) : (
        // 非零退出码是排查的起点，标红让它在一列里跳出来
        <Typography.Text type={code === 0 ? 'secondary' : 'danger'}>{code}</Typography.Text>
      ),
  },
  {
    title: '提交时间',
    dataIndex: field<Run>('created_at'),
    width: 110,
    render: (value: string | null) => <RelativeTime value={value} />,
  },
  {
    title: '调度任务',
    dataIndex: field<Run>('scheduler_job_id'),
    width: 180,
    render: (jobId: string | null) =>
      jobId ? <Mono copyable>{jobId}</Mono> : <Typography.Text type="secondary">—</Typography.Text>,
  },
]

interface Props {
  runs: Run[]
  /** 不传表示这是一个不分页的短列表（比如首页的最近 Run）。 */
  pagination?: TablePaginationConfig | false
}

export function RunTable({ runs, pagination = false }: Props) {
  return (
    <Table rowKey="id" size="small" dataSource={runs} columns={columns} pagination={pagination} />
  )
}
