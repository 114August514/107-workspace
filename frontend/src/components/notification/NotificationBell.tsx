import { BellIcon } from '@primer/octicons-react'
import { AnchoredOverlay, Banner, Button, CounterLabel, Label, Link, Text } from '@primer/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { api } from '../../api/client'
import type { AsyncErrorView } from '../../api/errors'
import { toAsyncError } from '../../api/errors'
import type { Notification, NotificationPage, NotificationPreference } from '../../api/types'
import { useAsync, usePolling } from '../../api/useAsync'
import { formatRelative, formatTime } from '../../utils/format'
import { AsyncState } from '../common/AsyncState'
import { notificationLabel, notificationPath, notificationVariant } from './notificationTypes'
import styles from './NotificationBell.module.css'

const POLL_INTERVAL_MS = 30_000

interface Props {
  username: string
}

export function NotificationBell({ username }: Props) {
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const requestSequence = useRef(0)

  const refreshCount = useCallback(async () => {
    const sequence = ++requestSequence.current
    try {
      const count = await api.unreadCount()
      if (sequence === requestSequence.current) setUnread(count)
    } catch {
      // 通知中心不可用时不打断当前页面。
    }
  }, [])

  useEffect(() => {
    void refreshCount()
  }, [refreshCount, username])

  usePolling(() => void refreshCount(), POLL_INTERVAL_MS, true)

  return (
    <AnchoredOverlay
      open={open}
      onOpen={() => setOpen(true)}
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
  const [token, setToken] = useState(0)
  const [preferencesOpen, setPreferencesOpen] = useState(false)
  const [markError, setMarkError] = useState<AsyncErrorView | null>(null)
  const notifications = useAsync<NotificationPage>(
    () => api.listNotifications({ page_size: 30 }),
    [username, token],
  )
  const preferences = useAsync<NotificationPreference[]>(
    () => api.listNotificationPreferences(),
    [username],
  )

  const reload = () => setToken((n) => n + 1)
  const mark = async (notification: Notification) => {
    setMarkError(null)
    try {
      if (notification.read_at) await api.markNotificationUnread(notification.id)
      else await api.markNotificationRead(notification.id)
      reload()
      onChanged()
    } catch (error) {
      setMarkError(toAsyncError(error as Error) ?? null)
    }
  }

  const markAll = async () => {
    setMarkError(null)
    try {
      await api.markAllNotificationsRead()
      reload()
      onChanged()
    } catch (error) {
      setMarkError(toAsyncError(error as Error) ?? null)
    }
  }

  const updatePreference = async (preference: NotificationPreference) => {
    try {
      await api.setNotificationPreference(preference.type, !preference.enabled)
      preferences.reload()
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
        <div>
          {hasUnread && (
            <Button variant="invisible" size="small" onClick={markAll}>
              全部标为已读
            </Button>
          )}
          <Button
            variant="invisible"
            size="small"
            onClick={() => setPreferencesOpen((open) => !open)}
          >
            {preferencesOpen ? '收起设置' : '通知设置'}
          </Button>
        </div>
      </div>
      {markError && (
        <div className={styles.panelBanner}>
          <Banner variant="critical">
            <Banner.Title>{markError.message}</Banner.Title>
          </Banner>
        </div>
      )}
      {preferencesOpen && (
        <div className={styles.panelBody} aria-label="通知设置">
          <AsyncState
            loading={preferences.loading}
            loadingText="正在加载通知设置…"
            error={toAsyncError(preferences.error)}
            onRetry={preferences.reload}
          >
            {preferences.data && (
              <>
                <Text weight="semibold">可选通知</Text>
                <ul>
                  {preferences.data
                    .filter((preference) => !preference.mandatory)
                    .map((preference) => (
                      <li key={preference.type}>
                        <label>
                          <input
                            type="checkbox"
                            checked={preference.enabled}
                            onChange={() => void updatePreference(preference)}
                          />{' '}
                          {notificationLabel(preference.type)}
                        </label>
                      </li>
                    ))}
                </ul>
                <Text weight="semibold">重要系统通知</Text>
                <ul>
                  {preferences.data
                    .filter((preference) => preference.mandatory)
                    .map((preference) => (
                      <li key={preference.type}>
                        <label>
                          <input
                            type="checkbox"
                            checked={preference.enabled}
                            disabled
                            readOnly
                            aria-label={`${notificationLabel(preference.type)}（始终开启）`}
                          />{' '}
                          {notificationLabel(preference.type)} <Label size="small">始终开启</Label>
                        </label>
                      </li>
                    ))}
                </ul>
                <Text>重要系统通知始终开启。</Text>
              </>
            )}
          </AsyncState>
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
          emptyDescription="收到 User Group 邀请、Run 结束时，这里会出现提醒。"
        >
          <ul className={styles.list}>
            {items.map((notification) => (
              <NotificationLine
                key={notification.id}
                notification={notification}
                onToggle={() => mark(notification)}
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
  onToggle,
  onNavigate,
}: {
  notification: Notification
  onToggle: () => Promise<void>
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
    <li className={unread ? styles.itemUnread : styles.item}>
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
        <Link
          as={RouterLink}
          to={path}
          onClick={() => {
            if (unread) void onToggle()
            onNavigate()
          }}
        >
          {title}
        </Link>
      ) : (
        title
      )}
      <Button
        className={styles.readAction}
        variant="invisible"
        size="small"
        aria-label={
          unread ? `将「${notification.title}」标为已读` : `将「${notification.title}」标为未读`
        }
        onClick={() => void onToggle()}
      >
        {unread ? '标为已读' : '标为未读'}
      </Button>
      {notification.body && <div className={styles.itemBody}>{notification.body}</div>}
    </li>
  )
}
