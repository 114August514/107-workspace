import { Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'

import type { UserGroup } from '../../api/types'
import { field } from '../../utils/field'
import { RelativeTime } from '../common/Mono'

const columns: ColumnsType<UserGroup> = [
  {
    title: '名称',
    dataIndex: field<UserGroup>('name'),
    width: 220,
    render: (name: string, userGroup) => (
      <Link to={`/user-groups/${userGroup.id}`} style={{ fontWeight: 500 }}>
        {name}
      </Link>
    ),
  },
  {
    title: '说明',
    dataIndex: field<UserGroup>('description'),
    ellipsis: true,
    render: (description: string) => (
      <Typography.Text type="secondary">{description || '—'}</Typography.Text>
    ),
  },
  {
    title: '创建时间',
    dataIndex: field<UserGroup>('created_at'),
    width: 120,
    render: (value: string | null) => <RelativeTime value={value} />,
  },
]

export function WorkspaceTable({ userGroups }: { userGroups: UserGroup[] }) {
  return (
    <Table rowKey="id" size="small" dataSource={userGroups} columns={columns} pagination={false} />
  )
}
