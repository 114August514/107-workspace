import { SearchIcon } from '@primer/octicons-react'
import { TextInput } from '@primer/react'
import { useMemo, useState, type ReactNode } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { AsyncState } from '../common/AsyncState'
import { RepoTypeNav } from './RepoTypeNav'
import { matchesRepoType, useRepoTypeFilter, type RepoTypeFlags } from './repoType'
import styles from './repoList.module.css'
import { userGroupPageCopy as copy } from './userGroupCopy'

export interface RepoListItem {
  id: string
  name: string
  to: string
  description: string
  badges?: ReactNode
  topics?: ReactNode
  meta?: ReactNode
  types: RepoTypeFlags
}

interface Props {
  titleId: string
  listLabel: string
  searchPlaceholder: string
  countLabel: (count: number) => string
  noMatches: string
  loading: boolean
  loadingText: string
  error?: { message: string; problems?: string[]; requestId?: string }
  onRetry?: () => void
  emptyText: string
  emptyDescription?: string
  items: RepoListItem[]
  truncatedNote?: string | null
}

export function RepoList({
  titleId,
  listLabel,
  searchPlaceholder,
  countLabel,
  noMatches,
  loading,
  loadingText,
  error,
  onRetry,
  emptyText,
  emptyDescription,
  items,
  truncatedNote,
}: Props) {
  const type = useRepoTypeFilter()
  const [query, setQuery] = useState('')
  const normalized = query.trim().toLowerCase()
  const visible = useMemo(() => {
    return items.filter((item) => {
      if (!matchesRepoType(item.types, type)) return false
      if (!normalized) return true
      const haystack = `${item.name} ${item.description}`.toLowerCase()
      return haystack.includes(normalized)
    })
  }, [items, normalized, type])

  const showFilterMiss = !loading && !error && items.length > 0 && visible.length === 0

  return (
    <div className={styles.layout}>
      <RepoTypeNav />
      <section className={styles.section} aria-labelledby={titleId}>
        <div className={styles.sectionInner}>
          <h2 id={titleId} className={styles.title}>
            {copy.list.types[type]}
          </h2>
          <div className={styles.search}>
            <TextInput
              block
              aria-label={searchPlaceholder}
              placeholder={searchPlaceholder}
              value={query}
              trailingVisual={SearchIcon}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className={styles.box}>
            {!loading && !error ? (
              <div className={styles.boxHeader}>
                <p className={styles.count}>{countLabel(visible.length)}</p>
              </div>
            ) : null}
            <AsyncState
              loading={loading}
              loadingText={loadingText}
              error={error}
              onRetry={onRetry}
              empty={!loading && items.length === 0}
              emptyText={emptyText}
              emptyDescription={emptyDescription}
            >
              {showFilterMiss ? (
                <p className={styles.noResults}>{noMatches}</p>
              ) : (
                <ul className={styles.list} aria-label={listLabel}>
                  {visible.map((item) => (
                    <li key={item.id} className={styles.row}>
                      <div className={styles.titleRow}>
                        <h3 className={styles.itemTitle}>
                          <RouterLink className={styles.name} to={item.to}>
                            {item.name}
                          </RouterLink>
                        </h3>
                        {item.badges ? <span className={styles.badges}>{item.badges}</span> : null}
                      </div>
                      {item.description ? (
                        <p className={styles.description}>{item.description}</p>
                      ) : null}
                      {item.topics ? <div className={styles.topics}>{item.topics}</div> : null}
                      {item.meta ? <div className={styles.meta}>{item.meta}</div> : null}
                    </li>
                  ))}
                </ul>
              )}
              {truncatedNote ? <p className={styles.truncatedNote}>{truncatedNote}</p> : null}
            </AsyncState>
          </div>
        </div>
      </section>
    </div>
  )
}
