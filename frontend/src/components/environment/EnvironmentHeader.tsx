import { HomeIcon, VersionsIcon, HistoryIcon } from '@primer/octicons-react'
import { Button, UnderlineNav } from '@primer/react'
import type { ReactNode } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'
import { api } from '../../api/client'
import { useAsync } from '../../api/useAsync'
import styles from '../layout/AppShell.module.css'
import {
  EnvironmentContext,
  useCurrentEnvironment,
  type EnvironmentDetail,
} from './environmentContext'

export function EnvironmentProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const environmentId = matchPath('/environments/:environmentId', pathname)?.params.environmentId
  const versionId = matchPath('/environment-versions/:versionId', pathname)?.params.versionId
  const state = useAsync<EnvironmentDetail | null>(async () => {
    if (versionId) {
      const version = await api.environmentVersion(versionId)
      return { environment: await api.environment(version.environment_id), version }
    }
    return environmentId ? { environment: await api.environment(environmentId) } : null
  }, [environmentId, versionId])
  // Never expose a previous route's owner or capabilities during navigation.
  const current = state.data
  const belongs =
    current &&
    (versionId
      ? current.version?.id === versionId
      : current.environment.id === environmentId && !current.version)
  return (
    <EnvironmentContext.Provider value={{ ...state, data: belongs ? current : null }}>
      {children}
    </EnvironmentContext.Provider>
  )
}

export function EnvironmentHeaderContext() {
  const { data } = useCurrentEnvironment()
  if (!data) return null
  const { environment } = data
  return (
    <div className={styles.projectContext} role="group" aria-label="运行环境上下文">
      <Button
        as={Link}
        to={environment.owner.kind === 'user_group' ? `/user-groups/${environment.owner.id}` : '/'}
        variant="invisible"
        className={`${styles.projectContextItem} ${styles.projectOwner}`}
      >
        <span className={styles.projectContextLabel}>{environment.owner.display_name}</span>
      </Button>
      <span className={styles.projectSeparator} aria-hidden>
        /
      </span>
      <Button
        as={Link}
        to={`/environments/${environment.id}`}
        variant="invisible"
        className={`${styles.projectContextItem} ${styles.projectName}`}
      >
        <span className={styles.projectContextLabel}>{environment.name}</span>
      </Button>
    </div>
  )
}

export function EnvironmentHeaderNav() {
  const { data } = useCurrentEnvironment()
  const { search } = useLocation()
  if (!data) return null
  const tab = data.version ? 'versions' : (new URLSearchParams(search).get('tab') ?? 'overview')
  const sections = [
    { key: 'overview', label: '概览', icon: <HomeIcon /> },
    { key: 'versions', label: '版本', icon: <VersionsIcon /> },
  ]
  if (data.environment.capabilities?.includes('environment.version.create'))
    sections.push({ key: 'history', label: '发布记录', icon: <HistoryIcon /> })
  return (
    <div className={styles.projectNavigationSurface}>
      <UnderlineNav
        aria-label="运行环境导航"
        className={styles.projectNavigation}
        hideIconsBreakpoint={null}
      >
        {sections.map((section) => (
          <UnderlineNav.Item
            key={section.key}
            as={Link}
            to={`/environments/${data.environment.id}?tab=${section.key}`}
            leadingVisual={section.icon}
            aria-current={tab === section.key ? 'page' : undefined}
          >
            {section.label}
          </UnderlineNav.Item>
        ))}
      </UnderlineNav>
    </div>
  )
}
