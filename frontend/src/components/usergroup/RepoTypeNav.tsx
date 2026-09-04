import {
  ArchiveIcon,
  GlobeIcon,
  PersonIcon,
  RepoForkedIcon,
  RepoIcon,
  RepoTemplateIcon,
  ShieldLockIcon,
} from '@primer/octicons-react'
import { NavList } from '@primer/react'
import { Link as RouterLink, useLocation } from 'react-router-dom'

import { useRepoTypeFilter, type RepoTypeFilter } from './repoType'
import { userGroupPageCopy as copy } from './userGroupCopy'
import styles from './repoList.module.css'

const TYPE_ICONS: Record<RepoTypeFilter, typeof RepoIcon> = {
  all: RepoIcon,
  contributed: PersonIcon,
  admin: ShieldLockIcon,
  public: GlobeIcon,
  sources: RepoIcon,
  forks: RepoForkedIcon,
  archived: ArchiveIcon,
  templates: RepoTemplateIcon,
}

export function RepoTypeNav({ types }: { types: readonly RepoTypeFilter[] }) {
  const { pathname } = useLocation()
  const active = useRepoTypeFilter(types)

  return (
    <div className={styles.sidebar}>
      <NavList aria-label={copy.list.typeNavLabel}>
        <NavList.Group title={copy.list.typeNavLabel}>
          {types.map((type) => {
            const Icon = TYPE_ICONS[type]
            return (
              <NavList.Item
                key={type}
                as={RouterLink}
                to={type === 'all' ? pathname : `${pathname}?type=${type}`}
                aria-current={active === type ? 'page' : undefined}
              >
                <span className={styles.typeItem}>
                  <span className={styles.typeIcon} aria-hidden>
                    <Icon />
                  </span>
                  <span className={styles.typeLabel}>{copy.list.types[type]}</span>
                </span>
              </NavList.Item>
            )
          })}
        </NavList.Group>
      </NavList>
    </div>
  )
}
