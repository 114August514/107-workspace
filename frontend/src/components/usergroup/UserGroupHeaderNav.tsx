/**
 * App Header 第二行的 User Group 分区导航,及其数据 Provider。
 *
 * 组详情数据由 Provider 统一加载:Header 导航与 UserGroupPage 共享同一份
 * async state,成员变更等 mutation 走 Outlet context 的 reload 时,
 * 两处的 capability(如「设置」入口)同时刷新,不会出现一份新一份旧。
 */
import { UnderlineNav } from '@primer/react'
import type { ReactNode } from 'react'
import { Link as RouterLink, matchPath, useLocation } from 'react-router-dom'

import { api } from '../../api/client'
import type { UserGroup } from '../../api/types'
import { can } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { UserGroupContext, useCurrentUserGroup, type CurrentUserGroup } from './userGroupContext'
import { userGroupPageCopy as copy } from './userGroupCopy'
import styles from './UserGroupHeaderNav.module.css'

const USER_GROUP_ROUTE_PATTERN = '/user-groups/:userGroupId/*'

export function UserGroupProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const match = matchPath(USER_GROUP_ROUTE_PATTERN, pathname)
  const userGroupId = match?.params.userGroupId ?? ''

  const state = useAsync<UserGroup | null>(
    () => (userGroupId ? api.getUserGroup(userGroupId) : Promise.resolve(null)),
    [userGroupId],
  )

  const value: CurrentUserGroup = {
    userGroupId: userGroupId || undefined,
    userGroup: state.data ?? undefined,
    loading: state.loading,
    error: state.error,
    reload: state.reload,
  }

  return <UserGroupContext.Provider value={value}>{children}</UserGroupContext.Provider>
}

export function UserGroupHeaderNav() {
  const { userGroupId, userGroup } = useCurrentUserGroup()
  const { pathname } = useLocation()

  if (!userGroupId || !userGroup) return null

  const basePath = `/user-groups/${userGroupId}`
  const activeSection = pathname.startsWith(`${basePath}/`)
    ? pathname.slice(basePath.length + 1).split('/')[0] || 'overview'
    : 'overview'

  // 导航渲染在 AppShell,位于路由树之外,相对链接会按当前 URL 叠加解析,
  // 必须用绝对路径。
  const sections = [
    { key: 'overview', label: copy.nav.overview, to: basePath },
    { key: 'projects', label: copy.nav.projects, to: `${basePath}/projects` },
    {
      key: 'shared-resources',
      label: copy.nav.sharedResources,
      to: `${basePath}/shared-resources`,
    },
    { key: 'environments', label: copy.nav.environments, to: `${basePath}/environments` },
    { key: 'members', label: copy.nav.members, to: `${basePath}/members` },
    ...(can(userGroup, 'user_group.update')
      ? [{ key: 'settings', label: copy.nav.settings, to: `${basePath}/settings` }]
      : []),
  ]

  return (
    <div className={styles.contextNav}>
      <UnderlineNav aria-label={copy.page.navLabel}>
        {sections.map((section) => (
          <UnderlineNav.Item
            key={section.key}
            as={RouterLink}
            to={section.to}
            aria-current={activeSection === section.key ? 'page' : undefined}
          >
            {section.label}
          </UnderlineNav.Item>
        ))}
      </UnderlineNav>
    </div>
  )
}
