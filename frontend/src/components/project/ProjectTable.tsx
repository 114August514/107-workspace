import { Table, Tag, Typography } from 'antd'
import type { TablePaginationConfig } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'

import type { Project } from '../../api/types'
import { field } from '../../utils/field'
import { RelativeTime } from '../common/Mono'

const columns: ColumnsType<Project> = [
  {
    title: '名称',
    dataIndex: field<Project>('name'),
    width: 240,
    render: (name: string, project) => (
      <Link to={`/projects/${project.id}`} style={{ fontWeight: 500 }}>
        {name}
      </Link>
    ),
  },
  {
    title: '说明',
    dataIndex: field<Project>('description'),
    ellipsis: true,
    render: (description: string) => (
      <Typography.Text type="secondary">{description || '—'}</Typography.Text>
    ),
  },
  {
    title: '状态',
    dataIndex: field<Project>('status'),
    width: 100,
    render: (status: string) =>
      status === 'active' ? <Tag color="green">进行中</Tag> : <Tag>已归档</Tag>,
  },
  {
    title: '最近更新',
    dataIndex: field<Project>('updated_at'),
    width: 120,
    render: (value: string | null) => <RelativeTime value={value} />,
  },
]

interface Props {
  projects: Project[]
  /** 不传表示这是一个不分页的短列表（比如首页的最近 Project）。 */
  pagination?: TablePaginationConfig | false
}

export function ProjectTable({ projects, pagination = false }: Props) {
  return (
    <Table
      rowKey="id"
      size="small"
      dataSource={projects}
      columns={columns}
      pagination={pagination}
    />
  )
}
