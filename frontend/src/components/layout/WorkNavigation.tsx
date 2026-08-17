import { HomeIcon, OrganizationIcon, PersonIcon, ProjectIcon } from '@primer/octicons-react'
import { NavList } from '@primer/react'
import type { RefObject } from 'react'
import { Link as RouterLink, useLocation } from 'react-router-dom'

import type { Home } from '../../api/types'
import { workNavigationCopy } from './copy'
import styles from './WorkNavigation.module.css'

interface Props {
  home: Home
  onNavigate?: () => void
  homeLinkRef?: RefObject<HTMLAnchorElement | null>
}

/**
 * 当前用户的真实工作入口。
 *
 * 只展示 `/me` 已经返回的数据；首页常驻栏和壳层抽屉复用同一组件，
 * 组件本身不发请求，也不引入第二套数据流。
 */
export function WorkNavigation({ home, onNavigate, homeLinkRef }: Props) {
  const location = useLocation()
  const workspaceNames = new Map(home.workspaces.map((workspace) => [workspace.id, workspace.name]))

  return (
    <NavList aria-label={workNavigationCopy.ariaLabel} className={styles.navigation}>
      <NavList.Heading>{workNavigationCopy.heading}</NavList.Heading>
      <NavList.Item
        className={styles.item}
        as={RouterLink}
        to="/"
        ref={homeLinkRef}
        aria-current={location.pathname === '/' ? 'page' : undefined}
        onClick={onNavigate}
      >
        <NavList.LeadingVisual>
          <HomeIcon />
        </NavList.LeadingVisual>
        <span className={styles.itemText}>{workNavigationCopy.home}</span>
      </NavList.Item>
      <NavList.Group title={workNavigationCopy.workspaceGroup}>
        {home.workspaces.length === 0 ? (
          <li className={styles.empty}>{workNavigationCopy.workspaceEmpty}</li>
        ) : (
          home.workspaces.map((workspace) => (
            <NavList.Item
              className={styles.item}
              key={workspace.id}
              as={RouterLink}
              to={`/workspaces/${workspace.id}`}
              aria-current={
                location.pathname === `/workspaces/${workspace.id}` ? 'page' : undefined
              }
              onClick={onNavigate}
            >
              <NavList.LeadingVisual>
                {workspace.kind === 'personal' ? <PersonIcon /> : <OrganizationIcon />}
              </NavList.LeadingVisual>
              <span className={styles.itemText}>{workspace.name}</span>
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
              onClick={onNavigate}
            >
              <NavList.LeadingVisual>
                <ProjectIcon />
              </NavList.LeadingVisual>
              <span className={styles.itemContent}>
                <span className={styles.itemText}>{project.name}</span>
                {workspaceNames.get(project.workspace_id) ? (
                  <span className={styles.itemMeta}>
                    {workspaceNames.get(project.workspace_id)}
                  </span>
                ) : null}
              </span>
            </NavList.Item>
          ))
        )}
      </NavList.Group>
    </NavList>
  )
}
