import { ChevronDownIcon } from '@primer/octicons-react'
import { ActionList, ActionMenu, Button } from '@primer/react'

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
 *
 * 提示文案用原生 title：Primer Tooltip 包 ActionMenu.Anchor 会吃掉 ref 转发，
 * 锚点按钮拿不到浮层定位需要的 DOM 节点。
 */
export function UserSwitcher({ value, onChange }: Props) {
  return (
    <ActionMenu>
      <ActionMenu.Anchor>
        <Button
          variant="invisible"
          trailingVisual={ChevronDownIcon}
          aria-label={`切换身份，当前 ${value}`}
          title="开发模式身份切换；接入统一身份认证后会被登录态替代"
        >
          {value}
        </Button>
      </ActionMenu.Anchor>
      <ActionMenu.Overlay>
        <ActionList>
          {KNOWN_USERS.map((name) => (
            <ActionList.Item key={name} selected={name === value} onSelect={() => onChange(name)}>
              {name}
            </ActionList.Item>
          ))}
        </ActionList>
      </ActionMenu.Overlay>
    </ActionMenu>
  )
}
