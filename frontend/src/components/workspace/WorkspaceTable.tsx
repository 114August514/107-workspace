import { Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'

import type { Workspace } from '../../api/types'
import { field } from '../../utils/field'
import { RelativeTime } from '../common/Mono'

const columns: ColumnsType<Workspace> = [
  {
    title: '名称',
    dataIndex: field<Workspace>('name'),
    width: 220,
    render: (name: string, workspace) => (
      <Link to={`/workspaces/${workspace.id}`} style={{ fontWeight: 500 }}>
        {name}
      </Link>
    ),
  },
  {
    title: '类型',
    dataIndex: field<Workspace>('kind'),
    width: 100,
    render: (kind: string) =>
      kind === 'personal' ? <Tag>个人</Tag> : <Tag color="blue">协作</Tag>,
  },
  {
    title: '说明',
    dataIndex: field<Workspace>('description'),
    ellipsis: true,
    render: (description: string) => (
      <Typography.Text type="secondary">{description || '—'}</Typography.Text>
    ),
  },
  {
    title: '创建时间',
    dataIndex: field<Workspace>('created_at'),
    width: 120,
    render: (value: string | null) => <RelativeTime value={value} />,
  },
]

export function WorkspaceTable({ workspaces }: { workspaces: Workspace[] }) {
  return (
    <Table rowKey="id" size="small" dataSource={workspaces} columns={columns} pagination={false} />
  )
}
