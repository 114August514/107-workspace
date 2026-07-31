import { UserOutlined } from '@ant-design/icons'
import { Select, Space, Tooltip } from 'antd'

import { colors } from '../../theme'

const KNOWN_USERS = ['student', 'teacher', 'teammate']

interface Props {
  value: string
  onChange: (username: string) => void
}

/**
 * 开发身份切换器。
 *
 * 后端 auth_mode=dev 时用 X-User 请求头识别身份，这个控件就是它的界面。
 * 接入学校统一身份认证之后，这个组件会被真正的登录态替换掉。
 */
export function UserSwitcher({ value, onChange }: Props) {
  return (
    <Tooltip title="开发模式身份切换；接入统一身份认证后会被登录态替代">
      <Space>
        <UserOutlined style={{ color: colors.onDarkMuted }} />
        <Select
          value={value}
          onChange={onChange}
          style={{ minWidth: 140 }}
          options={KNOWN_USERS.map((name) => ({ value: name, label: name }))}
        />
      </Space>
    </Tooltip>
  )
}
