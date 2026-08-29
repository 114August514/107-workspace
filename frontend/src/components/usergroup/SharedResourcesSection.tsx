import { Link as RouterLink, useOutletContext } from 'react-router-dom'

import { toAsyncError } from '../../api/errors'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import styles from './assets.module.css'
import { loadGroupSharedResources } from './groupAssets'
import { userGroupPageCopy as copy } from './userGroupCopy'

export function SharedResourcesSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const resources = useAsync(() => loadGroupSharedResources(userGroup.id), [userGroup.id])
  const items = resources.data ?? []

  return (
    <section className={styles.section} aria-labelledby="user-group-shared-resources-title">
      <header className={styles.sectionHeader}>
        <h2 id="user-group-shared-resources-title" className={styles.sectionTitle}>
          {copy.sections.sharedResources.title}
        </h2>
        <p className={styles.sectionDescription}>{copy.sections.sharedResources.description}</p>
      </header>
      <AsyncState
        loading={resources.loading}
        loadingText="正在加载共享资源…"
        error={toAsyncError(resources.error)}
        onRetry={resources.reload}
        empty={!resources.loading && resources.data !== undefined && items.length === 0}
        emptyText="这个 User Group 还没有共享资源。"
        emptyDescription="组拥有的共享资源会出现在这里。"
      >
        <ul className={styles.assetList} aria-label="共享资源列表">
          {items.map((resource) => (
            <li key={resource.id}>
              <RouterLink className={styles.assetLink} to={`/shared-resources/${resource.id}`}>
                <span className={styles.itemMain}>
                  <span className={styles.itemTitle}>{resource.name}</span>
                  <span className={styles.itemMeta}>
                    {resource.description || '这个共享资源还没有填写说明。'}
                  </span>
                </span>
              </RouterLink>
            </li>
          ))}
        </ul>
      </AsyncState>
    </section>
  )
}
