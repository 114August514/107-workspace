import { BellIcon } from '@primer/octicons-react'
import { AnchoredOverlay, Banner, Button, CounterLabel, Label, Link, Text } from '@primer/react'
import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { api } from '../../api/client'
import type { AsyncErrorView } from '../../api/errors'
import { toAsyncError } from '../../api/errors'
import type { Notification, NotificationPage } from '../../api/types'
import { useAsync, usePolling } from '../../api/useAsync'
import { formatRelative, formatTime } from '../../utils/format'
import { AsyncState } from '../common/AsyncState'
import { notificationLabel, notificationPath, notificationVariant } from './notificationTypes'
import styles from './NotificationBell.module.css'

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
    <AnchoredOverlay
      open={open}
      onClose={() => setOpen(false)}
      renderAnchor={(props) => (
        <Button
          variant="invisible"
          leadingVisual={BellIcon}
          trailingVisual={unread > 0 ? <CounterLabel>{unread}</CounterLabel> : undefined}
          aria-label={unread > 0 ? `通知，${unread} 条未读` : '通知'}
          {...props}
        />
      )}
    >
      {/* 浮层内容只在展开时挂载，所以列表的加载状态每次打开都会重新走一遍 */}
      <NotificationPanel
        username={username}
        onClose={() => setOpen(false)}
        onChanged={refreshCount}
      />
    </AnchoredOverlay>
  )
}

interface PanelProps {
  username: string
  onClose: () => void
  onChanged: () => void
}

function NotificationPanel({ username, onClose, onChanged }: PanelProps) {
  // token 用来在标记已读之后重新拉列表
  const [token, setToken] = useState(0)
  // 标记已读失败就地显示在浮层里——顶栏操作不该再弹全局 toast
  const [markError, setMarkError] = useState<AsyncErrorView | null>(null)
  const notifications = useAsync<NotificationPage>(
    () => api.listNotifications({ page_size: 30 }),
    [username, token],
  )

  const markAll = async () => {
    setMarkError(null)
    try {
      await api.markAllNotificationsRead()
      setToken((n) => n + 1)
      onChanged()
    } catch (error) {
      setMarkError(toAsyncError(error as Error) ?? null)
    }
  }

  const markOne = async (notification: Notification) => {
    if (notification.read_at) return
    setMarkError(null)
    try {
      await api.markNotificationRead(notification.id)
      setToken((n) => n + 1)
      onChanged()
    } catch (error) {
      setMarkError(toAsyncError(error as Error) ?? null)
    }
  }

  const items = notifications.data?.items ?? []
  const hasUnread = items.some((n) => !n.read_at)

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <Text weight="semibold">通知</Text>
        {hasUnread && (
          <Button variant="invisible" size="small" onClick={markAll}>
            全部标为已读
          </Button>
        )}
      </div>
      {markError && (
        <div className={styles.panelBanner}>
          <Banner variant="critical">
            <Banner.Title>{markError.message}</Banner.Title>
          </Banner>
        </div>
      )}
      <div className={styles.panelBody}>
        <AsyncState
          loading={notifications.loading}
          loadingText="正在加载通知…"
          error={toAsyncError(notifications.error)}
          onRetry={notifications.reload}
          empty={items.length === 0}
          emptyText="还没有通知"
          emptyDescription="收到协作邀请、Run 结束时，这里会出现提醒。"
        >
          <ul className={styles.list}>
            {items.map((notification) => (
              <NotificationLine
                key={notification.id}
                notification={notification}
                onRead={() => markOne(notification)}
                onNavigate={onClose}
              />
            ))}
          </ul>
        </AsyncState>
      </div>
    </div>
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

  const title = unread ? (
    <span className={styles.titleUnread}>{notification.title}</span>
  ) : (
    <span className={styles.title}>{notification.title}</span>
  )

  return (
    <li className={unread ? styles.itemUnread : styles.item} onClick={onRead}>
      <div className={styles.itemMeta}>
        <Label size="small" variant={notificationVariant(notification.type)}>
          {notificationLabel(notification.type)}
        </Label>
        {notification.mandatory && <Label size="small">重要</Label>}
        <time
          className={styles.itemTime}
          dateTime={notification.created_at}
          title={formatTime(notification.created_at)}
        >
          {formatRelative(notification.created_at)}
        </time>
      </div>
      {path ? (
        <Link as={RouterLink} to={path} onClick={onNavigate}>
          {title}
        </Link>
      ) : (
        title
      )}
      {notification.body && <div className={styles.itemBody}>{notification.body}</div>}
    </li>
  )
}
