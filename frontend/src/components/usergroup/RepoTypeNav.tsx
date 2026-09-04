import { NavList } from '@primer/react'
import { Link as RouterLink, useLocation } from 'react-router-dom'

import { REPO_TYPE_FILTERS, useRepoTypeFilter } from './repoType'
import { userGroupPageCopy as copy } from './userGroupCopy'
import styles from './repoList.module.css'

export function RepoTypeNav() {
  const { pathname } = useLocation()
  const active = useRepoTypeFilter()

  return (
    <div className={styles.sidebar}>
      <NavList aria-label={copy.list.typeNavLabel}>
        <NavList.Group title={copy.list.typeNavLabel}>
          {REPO_TYPE_FILTERS.map((type) => (
            <NavList.Item
              key={type}
              as={RouterLink}
              to={type === 'all' ? pathname : `${pathname}?type=${type}`}
              aria-current={active === type ? 'page' : undefined}
            >
              <span className={styles.typeLabel}>{copy.list.types[type]}</span>
            </NavList.Item>
          ))}
        </NavList.Group>
      </NavList>
    </div>
  )
}
