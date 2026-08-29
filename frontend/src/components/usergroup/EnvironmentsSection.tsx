import { Label } from '@primer/react'
import { Link as RouterLink, useOutletContext } from 'react-router-dom'

import { toAsyncError } from '../../api/errors'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import styles from './assets.module.css'
import { loadGroupEnvironments } from './groupAssets'
import { userGroupPageCopy as copy } from './userGroupCopy'

export function EnvironmentsSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const environments = useAsync(() => loadGroupEnvironments(userGroup.id), [userGroup.id])
  const items = environments.data ?? []

  return (
    <section className={styles.section} aria-labelledby="user-group-environments-title">
      <header className={styles.sectionHeader}>
        <h2 id="user-group-environments-title" className={styles.sectionTitle}>
          {copy.sections.environments.title}
        </h2>
        <p className={styles.sectionDescription}>{copy.sections.environments.description}</p>
      </header>
      <AsyncState
        loading={environments.loading}
        loadingText="正在加载运行环境…"
        error={toAsyncError(environments.error)}
        onRetry={environments.reload}
        empty={!environments.loading && environments.data !== undefined && items.length === 0}
        emptyText="这个 User Group 还没有运行环境。"
        emptyDescription="组拥有的运行环境会出现在这里。"
      >
        <ul className={styles.assetList} aria-label="运行环境列表">
          {items.map((environment) => {
            const availableCount = environment.versions.filter(
              (version) => version.available,
            ).length
            return (
              <li key={environment.id}>
                <RouterLink className={styles.assetLink} to={`/environments/${environment.id}`}>
                  <span className={styles.itemMain}>
                    <span className={styles.itemTitle}>{environment.name}</span>
                    <span className={styles.itemMeta}>
                      {environment.description || '这个运行环境还没有填写说明。'}
                    </span>
                  </span>
                  <span className={styles.itemLabels}>
                    <Label variant={availableCount > 0 ? 'success' : 'attention'}>
                      {availableCount}/{environment.versions.length} 个版本可用
                    </Label>
                  </span>
                </RouterLink>
              </li>
            )
          })}
        </ul>
      </AsyncState>
    </section>
  )
}
