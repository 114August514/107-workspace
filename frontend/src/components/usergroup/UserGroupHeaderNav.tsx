/**
 * App Header 第二行的 User Group 分区导航,及其数据 Provider。
 *
 * 组详情数据由 Provider 统一加载:Header 导航与 UserGroupPage 共享同一份
 * async state,成员变更等 mutation 走 Outlet context 的 reload 时,
 * 两处的 capability(如「设置」入口)同时刷新,不会出现一份新一份旧。
 */
import {
  GearIcon,
  HomeIcon,
  PackageIcon,
  PeopleIcon,
  ProjectIcon,
  ServerIcon,
} from '@primer/octicons-react'
import { Button, UnderlineNav } from '@primer/react'
import type { ReactNode } from 'react'
import { Link as RouterLink, matchPath, useLocation } from 'react-router-dom'

import { api } from '../../api/client'
import type { UserGroup } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import shellStyles from '../layout/AppShell.module.css'
import { appShellCopy } from '../layout/copy'
import { UserGroupContext, useCurrentUserGroup, type CurrentUserGroup } from './userGroupContext'
import { userGroupPageCopy as copy } from './userGroupCopy'

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

export function UserGroupHeaderContext() {
  const { userGroupId, userGroup } = useCurrentUserGroup()
  if (!userGroupId || !userGroup) return null

  return (
    <div
      className={shellStyles.projectContext}
      role="group"
      aria-label={appShellCopy.userGroupContextLabel}
    >
      <Button
        as={RouterLink}
        to={`/user-groups/${userGroupId}`}
        variant="invisible"
        className={`${shellStyles.projectContextItem} ${shellStyles.projectName}`}
      >
        <span className={shellStyles.projectContextLabel}>{userGroup.name}</span>
      </Button>
    </div>
  )
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
    { key: 'overview', label: copy.nav.overview, to: basePath, icon: <HomeIcon /> },
    {
      key: 'projects',
      label: copy.nav.projects,
      to: `${basePath}/projects`,
      icon: <ProjectIcon />,
    },
    {
      key: 'shared-resources',
      label: copy.nav.sharedResources,
      to: `${basePath}/shared-resources`,
      icon: <PackageIcon />,
    },
    {
      key: 'environments',
      label: copy.nav.environments,
      to: `${basePath}/environments`,
      icon: <ServerIcon />,
    },
    { key: 'members', label: copy.nav.members, to: `${basePath}/members`, icon: <PeopleIcon /> },
    {
      key: 'settings',
      label: copy.nav.settings,
      to: `${basePath}/settings`,
      icon: <GearIcon />,
    },
  ]

  return (
    <div className={shellStyles.projectNavigationSurface}>
      <UnderlineNav
        aria-label={copy.page.navLabel}
        className={shellStyles.projectNavigation}
        hideIconsBreakpoint={null}
      >
        {sections.map((section) => (
          <UnderlineNav.Item
            key={section.key}
            as={RouterLink}
            to={section.to}
            leadingVisual={section.icon}
            aria-current={activeSection === section.key ? 'page' : undefined}
          >
            {section.label}
          </UnderlineNav.Item>
        ))}
      </UnderlineNav>
    </div>
  )
}
