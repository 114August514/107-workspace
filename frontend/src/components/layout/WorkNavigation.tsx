import { HomeIcon, OrganizationIcon, ProjectIcon } from '@primer/octicons-react'
import { NavList } from '@primer/react'
import { Link as RouterLink, useLocation } from 'react-router-dom'

import type { Home } from '../../api/types'
import { workNavigationCopy } from './copy'
import styles from './WorkNavigation.module.css'

interface Props {
  home: Home
}

/**
 * Home 页面常驻栏中的工作入口。
 *
 * 只展示 AppShell 已加载的 `/me` 数据，组件本身不发请求。
 */
export function WorkNavigation({ home }: Props) {
  const location = useLocation()
  const ownerNames = new Map(home.user_groups.map((userGroup) => [userGroup.id, userGroup.name]))
  if (home.personal_resource_context_id) {
    ownerNames.set(home.personal_resource_context_id, workNavigationCopy.personalResourceGroup)
  }

  return (
    <NavList aria-label={workNavigationCopy.ariaLabel} className={styles.navigation}>
      <NavList.Heading>{workNavigationCopy.heading}</NavList.Heading>
      <NavList.Item
        className={styles.item}
        as={RouterLink}
        to="/"
        aria-current={location.pathname === '/' ? 'page' : undefined}
      >
        <NavList.LeadingVisual>
          <HomeIcon />
        </NavList.LeadingVisual>
        <span className={styles.itemText}>{workNavigationCopy.home}</span>
      </NavList.Item>
      <NavList.Group title={workNavigationCopy.userGroupGroup}>
        {home.user_groups.length === 0 ? (
          <li className={styles.empty}>{workNavigationCopy.userGroupEmpty}</li>
        ) : (
          home.user_groups.map((userGroup) => (
            <NavList.Item
              className={styles.item}
              key={userGroup.id}
              as={RouterLink}
              to={`/user-groups/${userGroup.id}`}
              aria-current={
                location.pathname === `/user-groups/${userGroup.id}` ? 'page' : undefined
              }
            >
              <NavList.LeadingVisual>
                <OrganizationIcon />
              </NavList.LeadingVisual>
              <span className={styles.itemText}>{userGroup.name}</span>
            </NavList.Item>
          ))
        )}
      </NavList.Group>
      <NavList.Group title={workNavigationCopy.recentProjectsGroup}>
        {home.recent_projects.length === 0 ? (
          <li className={styles.empty}>{workNavigationCopy.recentProjectsEmpty}</li>
        ) : (
          home.recent_projects.map((project) => (
            <NavList.Item
              className={styles.item}
              key={project.id}
              as={RouterLink}
              to={`/projects/${project.id}`}
              aria-current={location.pathname === `/projects/${project.id}` ? 'page' : undefined}
            >
              <NavList.LeadingVisual>
                <ProjectIcon />
              </NavList.LeadingVisual>
              <span className={styles.itemContent}>
                <span className={styles.itemText}>{project.name}</span>
                {ownerNames.get(project.workspace_id) ? (
                  <span className={styles.itemMeta}>{ownerNames.get(project.workspace_id)}</span>
                ) : null}
              </span>
            </NavList.Item>
          ))
        )}
      </NavList.Group>
    </NavList>
  )
}
