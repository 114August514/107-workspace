import { Alert, Button, Space, Typography, message } from 'antd'

import { api } from '../../api/client'
import type { Invitation } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { roleLabel } from '../../utils/roles'
import { RelativeTime } from '../common/Mono'

interface Props {
  /** 切换身份时要重新拉——邀请是跟人走的。 */
  username: string
  /** 接受之后首页的空间列表要跟着刷新。 */
  onResponded: () => void
}

/**
 * 待处理的邀请。
 *
 * 放在首页而不是空间里：**被邀请的人还进不去那个空间**，
 * 空间列表只列已加入的，直接访问会 404，因为邀请尚未形成有效 Membership。
 * 早先没有这个入口，通知里写着「在空间列表里可以接受或拒绝」，
 * 指的是一个不存在的界面——收到邀请的人根本没有办法加入。
 *
 * 没有邀请时整块不渲染，不占首页的位置。
 */
export function InvitationList({ username, onResponded }: Props) {
  const invitations = useAsync<Invitation[]>(() => api.listInvitations(), [username])

  const respond = async (invitation: Invitation, accept: boolean) => {
    try {
      await api.respondToInvitation(invitation.workspace_id, accept)
      message.success(accept ? `已加入「${invitation.workspace_name}」` : '已拒绝邀请')
      invitations.reload()
      onResponded()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const items = invitations.data ?? []
  if (invitations.loading || items.length === 0) return null

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      {items.map((invitation) => (
        <Alert
          key={invitation.workspace_id}
          type="info"
          showIcon
          message={
            <Space wrap size={8}>
              <Typography.Text strong>{invitation.workspace_name}</Typography.Text>
              <Typography.Text type="secondary">
                {`邀请你以「${roleLabel(invitation.role)}」身份加入`}
              </Typography.Text>
              <RelativeTime value={invitation.invited_at} />
            </Space>
          }
          description={invitation.workspace_description || undefined}
          action={
            <Space>
              <Button size="small" onClick={() => respond(invitation, false)}>
                拒绝
              </Button>
              <Button size="small" type="primary" onClick={() => respond(invitation, true)}>
                接受
              </Button>
            </Space>
          }
        />
      ))}
    </Space>
  )
}
