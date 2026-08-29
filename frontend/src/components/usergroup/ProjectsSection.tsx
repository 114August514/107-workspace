import { Label } from '@primer/react'
import { Link as RouterLink, useOutletContext } from 'react-router-dom'

import { toAsyncError } from '../../api/errors'
import { useAsync } from '../../api/useAsync'
import { formatRelative } from '../../utils/format'
import { AsyncState } from '../common/AsyncState'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import styles from './assets.module.css'
import { loadGroupProjects } from './groupAssets'
import { userGroupPageCopy as copy } from './userGroupCopy'

export function ProjectsSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const projects = useAsync(() => loadGroupProjects(userGroup.id), [userGroup.id])
  const items = projects.data?.items ?? []

  return (
    <section className={styles.section} aria-labelledby="user-group-projects-title">
      <header className={styles.sectionHeader}>
        <h2 id="user-group-projects-title" className={styles.sectionTitle}>
          {copy.sections.projects.title}
        </h2>
        <p className={styles.sectionDescription}>{copy.sections.projects.description}</p>
      </header>
      <AsyncState
        loading={projects.loading}
        loadingText="正在加载 Project…"
        error={toAsyncError(projects.error)}
        onRetry={projects.reload}
        empty={!projects.loading && projects.data !== undefined && items.length === 0}
        emptyText="这个 User Group 还没有 Project。"
        emptyDescription="组拥有的 Project 会出现在这里。"
      >
        <ul className={styles.assetList} aria-label="Project 列表">
          {items.map((project) => (
            <li key={project.id}>
              <RouterLink className={styles.assetLink} to={`/projects/${project.id}`}>
                <span className={styles.itemMain}>
                  <span className={styles.itemTitle}>{project.name}</span>
                  <span className={styles.itemMeta}>
                    {project.description || '这个 Project 还没有填写说明。'}
                  </span>
                </span>
                <span className={styles.itemLabels}>
                  {project.status === 'archived' ? <Label variant="attention">已归档</Label> : null}
                  {project.updated_at ? (
                    <Label size="small" variant="default">
                      更新于 {formatRelative(project.updated_at)}
                    </Label>
                  ) : null}
                </span>
              </RouterLink>
            </li>
          ))}
        </ul>
        {projects.data?.truncated ? (
          <p className={styles.truncatedNote}>列表过长，仅显示前一部分 Project。</p>
        ) : null}
      </AsyncState>
    </section>
  )
}
