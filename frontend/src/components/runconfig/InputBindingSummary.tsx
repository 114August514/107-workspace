import { Space, Tag, Typography } from 'antd'

import type { InputBinding } from '../../api/types'

interface Props {
  bindings: InputBinding[]
  checking: boolean
  preflightOk: boolean | null
}

function availabilityTag(checking: boolean, preflightOk: boolean | null) {
  if (checking) return <Tag>检查中</Tag>
  if (preflightOk === true) return <Tag color="green">当前可用</Tag>
  if (preflightOk === false) return <Tag color="orange">未确认，请查看检查问题</Tag>
  return <Tag>尚未检查</Tag>
}

export function InputBindingSummary({ bindings, checking, preflightOk }: Props) {
  if (bindings.length === 0) return <>—</>

  return (
    <Space direction="vertical" size={6}>
      {bindings.map((binding) => (
        <Space
          key={`${binding.source_type}:${binding.source_id}:${binding.access_path}`}
          wrap
          size={6}
        >
          <Typography.Text>
            {binding.source_type === 'shared_resource_version' ? '资源版本' : '运行产物'}{' '}
            {binding.source_id}
          </Typography.Text>
          {binding.source_subpath && (
            <Typography.Text type="secondary">来源子路径 {binding.source_subpath}</Typography.Text>
          )}
          <Typography.Text code>输入访问路径 {binding.access_path}</Typography.Text>
          {availabilityTag(checking, preflightOk)}
        </Space>
      ))}
    </Space>
  )
}
