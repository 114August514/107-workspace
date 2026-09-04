import { CalendarIcon, ChevronRightIcon, PeopleIcon, ProjectIcon } from '@primer/octicons-react'
import { Link as RouterLink, useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import type { Member } from '../../api/types'
import { toAsyncError } from '../../api/errors'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { formatDate, formatRelative } from '../../utils/format'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupProjects } from './groupAssets'
import { userGroupPageCopy as copy } from './userGroupCopy'
import styles from './overview.module.css'

const PREVIEW_LIMIT = 5

export function OverviewSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const projects = useAsync(() => loadGroupProjects(userGroup.id), [userGroup.id])
  const members = useAsync<Member[]>(() => api.listMembers(userGroup.id), [userGroup.id])
  const items = (projects.data?.items ?? []).slice(0, PREVIEW_LIMIT)
  const truncated = (projects.data?.items.length ?? 0) > PREVIEW_LIMIT || projects.data?.truncated
  const activeMembers = members.data?.filter((member) => member.status === 'active').length ?? 0

  return (
    <div className={styles.layout}>
      <section className={styles.section} aria-labelledby="overview-projects-title">
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle} id="overview-projects-title">
            {copy.sections.projects.title}
          </h2>
          <RouterLink className={styles.sectionLink} to="projects">
            {copy.overview.viewAll}
          </RouterLink>
        </div>
        <AsyncState
          loading={projects.loading && !projects.data}
          loadingText={copy.overview.loading}
          error={toAsyncError(projects.error)}
          onRetry={projects.reload}
          empty={!projects.loading && items.length === 0}
          emptyText={copy.overview.emptyProjects}
        >
          <ul className={styles.rowList}>
            {items.map((project) => {
              const updated = project.updated_at ?? project.created_at
              return (
                <li key={project.id} className={styles.row}>
                  <RouterLink className={styles.rowLink} to={`/projects/${project.id}`}>
                    <span className={styles.rowIcon} aria-hidden="true">
                      <ProjectIcon size={16} />
                    </span>
                    <span className={styles.rowBody}>
                      <span className={styles.rowName}>{project.name}</span>
                      <span className={styles.rowDescription}>
                        {project.description || copy.overview.emptyDescription}
                      </span>
                      {updated ? (
                        <span className={styles.rowMeta}>更新于 {formatRelative(updated)}</span>
                      ) : null}
                    </span>
                    <ChevronRightIcon className={styles.rowChevron} size={16} aria-hidden="true" />
                  </RouterLink>
                </li>
              )
            })}
          </ul>
          {truncated ? <p className={styles.truncatedNote}>{copy.overview.truncated}</p> : null}
        </AsyncState>
      </section>

      <aside className={styles.about} aria-labelledby="overview-about-title">
        <h2 className={styles.aboutTitle} id="overview-about-title">
          {copy.overview.about}
        </h2>
        <p className={styles.aboutDescription}>
          {userGroup.description || copy.page.fallbackDescription}
        </p>
        {activeMembers > 0 ? (
          <p className={styles.aboutMeta}>
            <PeopleIcon className={styles.aboutMetaIcon} size={16} aria-hidden="true" />
            {`${activeMembers} 位成员`}
          </p>
        ) : null}
        {userGroup.created_at ? (
          <p className={styles.aboutMeta}>
            <CalendarIcon className={styles.aboutMetaIcon} size={16} aria-hidden="true" />
            {copy.overview.createdAt(formatDate(userGroup.created_at))}
          </p>
        ) : null}
      </aside>
    </div>
  )
}
