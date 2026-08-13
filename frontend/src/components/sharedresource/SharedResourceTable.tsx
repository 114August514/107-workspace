import { Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'

import type { SharedResource } from '../../api/types'
import { field } from '../../utils/field'
import { RelativeTime } from '../common/Mono'

const columns: ColumnsType<SharedResource> = [
  {
    title: '名称',
    dataIndex: field<SharedResource>('name'),
    width: 240,
    render: (name: string, resource) => (
      <Link to={`/shared-resources/${resource.id}`} style={{ fontWeight: 500 }}>
        {name}
      </Link>
    ),
  },
  {
    title: '说明',
    dataIndex: field<SharedResource>('description'),
    ellipsis: true,
    render: (description: string) => (
      <Typography.Text type="secondary">{description || '—'}</Typography.Text>
    ),
  },
  {
    title: '归属',
    dataIndex: field<SharedResource>('is_platform_owned'),
    width: 110,
    render: (isPlatform: boolean) =>
      isPlatform ? <Tag color="purple">平台</Tag> : <Tag>本空间</Tag>,
  },
  {
    title: '创建时间',
    dataIndex: field<SharedResource>('created_at'),
    width: 130,
    render: (value: string) => <RelativeTime value={value} />,
  },
]

interface Props {
  resources: SharedResource[]
}

export function SharedResourceTable({ resources }: Props) {
  return (
    <Table rowKey="id" size="small" dataSource={resources} columns={columns} pagination={false} />
  )
}
