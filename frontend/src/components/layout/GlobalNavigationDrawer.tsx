import {
  ContainerIcon,
  OrganizationIcon,
  PersonIcon,
  ProjectIcon,
  XIcon,
} from '@primer/octicons-react'
import { Button, Dialog, IconButton, NavList, type DialogHeaderProps } from '@primer/react'
import { useRef, useState, type RefObject } from 'react'
import { Link as RouterLink, useLocation } from 'react-router-dom'

import type { Home } from '../../api/types'
import type { AsyncState as AsyncResource } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { BrandMark } from '../../brand/BrandMark'
import { globalNavigationCopy } from './copy'
import styles from './GlobalNavigationDrawer.module.css'

interface Props {
  id: string
  home: AsyncResource<Home>
  returnFocusRef: RefObject<HTMLElement | null>
  onClose: () => void
}

const defaultVisibleItemCount = 5

export function GlobalNavigationDrawer({ id, home, returnFocusRef, onClose }: Props) {
  const location = useLocation()
  const homeLinkRef = useRef<HTMLAnchorElement>(null)
  const [showAllUserGroups, setShowAllUserGroups] = useState(false)
  const [showAllProjects, setShowAllProjects] = useState(false)
  const userGroups = home.data?.user_groups ?? []
  const projects = home.data?.recent_projects ?? []
  const visibleUserGroups = showAllUserGroups
    ? userGroups
    : userGroups.slice(0, defaultVisibleItemCount)
  const visibleProjects = showAllProjects ? projects : projects.slice(0, defaultVisibleItemCount)
  const hiddenUserGroupCount = userGroups.length - visibleUserGroups.length
  const hiddenProjectCount = projects.length - visibleProjects.length

  return (
    <Dialog
      title={globalNavigationCopy.title}
      position="left"
      width="medium"
      className={styles.drawer}
      initialFocusRef={homeLinkRef}
      returnFocusRef={returnFocusRef}
      renderHeader={DrawerHeader}
      onClose={onClose}
    >
      <Dialog.Body id={id} className={styles.body}>
        <AsyncState
          loading={home.loading}
          loadingText={globalNavigationCopy.loading}
          error={toNavigationError(home.error)}
          onRetry={home.reload}
        >
          {home.data ? (
            <NavList aria-label={globalNavigationCopy.ariaLabel} className={styles.navigation}>
              <NavList.Heading visuallyHidden>{globalNavigationCopy.heading}</NavList.Heading>
              {!location.pathname.startsWith('/projects/') &&
              !location.pathname.startsWith('/user-groups/') ? (
                <NavList.Item
                  className={styles.item}
                  as={RouterLink}
                  to="/"
                  ref={homeLinkRef}
                  aria-current={location.pathname === '/' ? 'page' : undefined}
                  onClick={onClose}
                >
                  <NavList.LeadingVisual>
                    <BrandMark size={16} decorative />
                  </NavList.LeadingVisual>
                  <span className={styles.itemText}>{globalNavigationCopy.title}</span>
                </NavList.Item>
              ) : null}

              <NavList.Item
                className={styles.item}
                as={RouterLink}
                to="/execution-context"
                aria-current={location.pathname === '/execution-context' ? 'page' : undefined}
                onClick={onClose}
              >
                <NavList.LeadingVisual>
                  <PersonIcon />
                </NavList.LeadingVisual>
                <span className={styles.itemText}>{globalNavigationCopy.executionContext}</span>
              </NavList.Item>

              <NavList.Item
                className={styles.item}
                as={RouterLink}
                to="/environments"
                aria-current={
                  location.pathname === '/environments' ||
                  location.pathname.startsWith('/environments/') ||
                  location.pathname.startsWith('/environment-versions/')
                    ? 'page'
                    : undefined
                }
                onClick={onClose}
              >
                <NavList.LeadingVisual>
                  <ContainerIcon />
                </NavList.LeadingVisual>
                <span className={styles.itemText}>{globalNavigationCopy.environments}</span>
              </NavList.Item>

              <NavList.Group title={globalNavigationCopy.userGroupsGroup}>
                {visibleUserGroups.length === 0 ? (
                  <li className={styles.empty}>{globalNavigationCopy.userGroupsEmpty}</li>
                ) : (
                  visibleUserGroups.map((userGroup) => (
                    <NavList.Item
                      className={styles.item}
                      key={userGroup.id}
                      as={RouterLink}
                      to={`/user-groups/${userGroup.id}`}
                      aria-current={
                        location.pathname === `/user-groups/${userGroup.id}` ? 'page' : undefined
                      }
                      onClick={onClose}
                    >
                      <NavList.LeadingVisual>
                        <OrganizationIcon />
                      </NavList.LeadingVisual>
                      <span className={styles.itemText}>{userGroup.name}</span>
                    </NavList.Item>
                  ))
                )}
                {hiddenUserGroupCount > 0 ? (
                  <li className={styles.expandItem}>
                    <Button
                      className={styles.expandButton}
                      variant="invisible"
                      aria-label={globalNavigationCopy.showRemainingUserGroups(
                        hiddenUserGroupCount,
                      )}
                      onClick={() => setShowAllUserGroups(true)}
                    >
                      {globalNavigationCopy.showRemaining(hiddenUserGroupCount)}
                    </Button>
                  </li>
                ) : null}
              </NavList.Group>

              <NavList.Group title={globalNavigationCopy.recentProjectsGroup}>
                {visibleProjects.length === 0 ? (
                  <li className={styles.empty}>{globalNavigationCopy.recentProjectsEmpty}</li>
                ) : (
                  visibleProjects.map((project) => (
                    <NavList.Item
                      className={styles.item}
                      key={project.id}
                      as={RouterLink}
                      to={`/projects/${project.id}`}
                      aria-current={
                        location.pathname === `/projects/${project.id}` ? 'page' : undefined
                      }
                      onClick={onClose}
                    >
                      <NavList.LeadingVisual>
                        <ProjectIcon />
                      </NavList.LeadingVisual>
                      <span className={styles.itemContent}>
                        <span className={styles.itemText}>{project.name}</span>
                        <span className={styles.itemMeta}>{project.owner.display_name}</span>
                      </span>
                    </NavList.Item>
                  ))
                )}
                {hiddenProjectCount > 0 ? (
                  <li className={styles.expandItem}>
                    <Button
                      className={styles.expandButton}
                      variant="invisible"
                      aria-label={globalNavigationCopy.showRemainingProjects(hiddenProjectCount)}
                      onClick={() => setShowAllProjects(true)}
                    >
                      {globalNavigationCopy.showRemaining(hiddenProjectCount)}
                    </Button>
                  </li>
                ) : null}
              </NavList.Group>
            </NavList>
          ) : null}
        </AsyncState>
      </Dialog.Body>
    </Dialog>
  )
}

function DrawerHeader({ dialogLabelId, onClose }: DialogHeaderProps) {
  return (
    <Dialog.Header className={styles.header}>
      <Dialog.Title id={dialogLabelId} className={styles.title}>
        {globalNavigationCopy.title}
      </Dialog.Title>
      <IconButton
        className={styles.closeButton}
        icon={XIcon}
        variant="invisible"
        aria-label={globalNavigationCopy.close}
        onClick={() => onClose('close-button')}
      />
    </Dialog.Header>
  )
}

function toNavigationError(error: Error | undefined) {
  if (!error) return undefined
  return {
    message: globalNavigationCopy.error,
    problems: [globalNavigationCopy.errorNextStep],
  }
}
