import { BellOutlined } from '@ant-design/icons'
import { Badge, Button, Drawer, List, Space, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../api/client'
import type { Notification, NotificationPage } from '../../api/types'
import { useAsync, usePolling } from '../../api/useAsync'
import { colors } from '../../theme'
import { AsyncSection } from '../common/AsyncSection'
import { RelativeTime } from '../common/Mono'
import { notificationColor, notificationLabel, notificationPath } from './notificationTypes'

/** 未读数的轮询间隔。和 Run 状态轮询共用同一套 usePolling。 */
const POLL_INTERVAL_MS = 30_000

interface Props {
  /** 切换身份时要重新拉取——未读数是跟人走的。 */
  username: string
}

export function NotificationBell({ username }: Props) {
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)

  const refreshCount = useCallback(async () => {
    try {
      setUnread(await api.unreadCount())
    } catch {
      // 未读数拉不到不值得打扰用户：铃铛上少个数字而已，
      // 弹一个报错反而更烦人。
    }
  }, [])

  useEffect(() => {
    void refreshCount()
  }, [refreshCount, username])

  // 30 秒一次，一直开着——未读数随时可能变（别人邀请你、你的 Run 跑完了）
  usePolling(() => void refreshCount(), POLL_INTERVAL_MS, true)

  return (
    <>
      <Badge
        count={unread}
        size="small"
        offset={[-2, 2]}
        // 顶栏是深色，默认的 colorError 在上面对比度只有 2.74:1。
        // 见 theme.ts 里 badgeOnDark 的说明。
        style={{
          backgroundColor: colors.badgeOnDark,
          color: colors.badgeOnDarkText,
          boxShadow: 'none',
          fontWeight: 600,
        }}
      >
        <Button
          type="text"
          aria-label="通知"
          icon={<BellOutlined style={{ color: colors.onDarkMuted, fontSize: 16 }} />}
          onClick={() => setOpen(true)}
        />
      </Badge>
      <NotificationDrawer
        open={open}
        username={username}
        onClose={() => setOpen(false)}
        onChanged={refreshCount}
      />
    </>
  )
}

interface DrawerProps {
  open: boolean
  username: string
  onClose: () => void
  onChanged: () => void
}

function NotificationDrawer({ open, username, onClose, onChanged }: DrawerProps) {
  // token 用来在标记已读之后重新拉列表
  const [token, setToken] = useState(0)
  const notifications = useAsync<NotificationPage>(
    () => api.listNotifications({ page_size: 30 }),
    [username, token, open],
  )

  const markAll = async () => {
    try {
      await api.markAllNotificationsRead()
      setToken((n) => n + 1)
      onChanged()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const markOne = async (notification: Notification) => {
    if (notification.read_at) return
    try {
      await api.markNotificationRead(notification.id)
      setToken((n) => n + 1)
      onChanged()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const items = notifications.data?.items ?? []
  const hasUnread = items.some((n) => !n.read_at)

  return (
    <Drawer
      title="通知"
      open={open}
      onClose={onClose}
      width={420}
      extra={
        hasUnread && (
          <Button size="small" onClick={markAll}>
            全部标为已读
          </Button>
        )
      }
    >
      <AsyncSection
        loading={notifications.loading}
        error={notifications.error}
        empty={items.length === 0}
        emptyText="还没有通知"
      >
        <List
          dataSource={items}
          renderItem={(notification) => (
            <NotificationLine
              notification={notification}
              onRead={() => markOne(notification)}
              onNavigate={onClose}
            />
          )}
        />
      </AsyncSection>
    </Drawer>
  )
}

function NotificationLine({
  notification,
  onRead,
  onNavigate,
}: {
  notification: Notification
  onRead: () => void
  onNavigate: () => void
}) {
  const path = notificationPath(notification)
  const unread = !notification.read_at

  const title = <Typography.Text strong={unread}>{notification.title}</Typography.Text>

  return (
    <List.Item
      onClick={onRead}
      style={{
        cursor: unread ? 'pointer' : 'default',
        // 未读的整条底色浅浅提一下。加粗一个字重不够明显，
        // 一屏十几条时扫不出来哪些还没看。
        background: unread ? colors.subtle : undefined,
        paddingInline: 12,
      }}
    >
      <Space direction="vertical" size={2} style={{ width: '100%' }}>
        <Space size={8} align="center" wrap>
          <Tag color={notificationColor(notification.type)}>
            {notificationLabel(notification.type)}
          </Tag>
          {notification.mandatory && <Tag>重要</Tag>}
          <RelativeTime value={notification.created_at} />
        </Space>
        {path ? (
          <Link to={path} onClick={onNavigate}>
            {title}
          </Link>
        ) : (
          title
        )}
        {notification.body && (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {notification.body}
          </Typography.Text>
        )}
      </Space>
    </List.Item>
  )
}
