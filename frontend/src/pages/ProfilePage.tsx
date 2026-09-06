import { CheckIcon, ChevronRightIcon, CopyIcon } from '@primer/octicons-react'
import { IconButton } from '@primer/react'
import { useEffect, useRef, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { toAsyncError } from '../api/errors'
import type { Home } from '../api/types'
import type { AsyncState as AsyncResource } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { membershipRoleLabel } from '../components/workspace/memberCopy'
import { profileCopy } from './profileCopy'
import styles from './ProfilePage.module.css'

interface Props {
  home: AsyncResource<Home>
}

export function ProfilePage({ home }: Props) {
  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>{profileCopy.title}</h1>
      </header>
      <AsyncState
        loading={home.loading}
        loadingText={profileCopy.loading}
        error={toAsyncError(home.error)}
        onRetry={home.reload}
      >
        {home.data ? <ProfileBody home={home.data} /> : null}
      </AsyncState>
    </div>
  )
}

function ProfileBody({ home }: { home: Home }) {
  const user = home.user
  const email = user.email?.trim() ? user.email : profileCopy.emailMissing
  const groups = home.user_groups

  return (
    <>
      <section className={styles.identity} aria-label={profileCopy.title}>
        <h2 className={styles.displayName}>{user.display_name}</h2>
        <p className={styles.username}>@{user.username}</p>
      </section>

      <section className={styles.section} aria-labelledby="profile-basics-title">
        <h2 id="profile-basics-title" className={styles.sectionTitle}>
          {profileCopy.basics}
        </h2>
        <div className={styles.panel}>
          <div className={styles.field}>
            <span className={styles.label}>{profileCopy.email}</span>
            <span className={styles.value}>{email}</span>
          </div>
          <div className={styles.field}>
            <span className={styles.label}>{profileCopy.userId}</span>
            <span className={`${styles.value} ${styles.userId}`}>{user.id}</span>
            <CopyUserId userId={user.id} />
          </div>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="profile-groups-title">
        <h2 id="profile-groups-title" className={styles.sectionTitle}>
          {profileCopy.groups}
        </h2>
        {groups.length === 0 ? (
          <p className={`${styles.panel} ${styles.empty}`}>{profileCopy.groupsEmpty}</p>
        ) : (
          <ul className={`${styles.panel} ${styles.list}`}>
            {groups.map((group) => (
              <li key={group.id} className={styles.row}>
                <RouterLink
                  className={styles.rowLink}
                  to={`/user-groups/${group.id}`}
                  aria-label={profileCopy.groupLink(group.name)}
                >
                  <span className={styles.rowName}>{group.name}</span>
                  <span className={styles.rowMeta}>{membershipRoleLabel(group.role)}</span>
                  <ChevronRightIcon className={styles.chevron} size={16} aria-hidden="true" />
                </RouterLink>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section} aria-labelledby="profile-settings-title">
        <h2 id="profile-settings-title" className={styles.sectionTitle}>
          {profileCopy.settings}
        </h2>
        <div className={styles.panel}>
          <RouterLink className={styles.rowLink} to="/execution-context">
            <span className={styles.rowName}>{profileCopy.executionContext}</span>
            <ChevronRightIcon className={styles.chevron} size={16} aria-hidden="true" />
          </RouterLink>
        </div>
      </section>
    </>
  )
}

function CopyUserId({ userId }: { userId: string }) {
  const [copied, setCopied] = useState(false)
  const [failed, setFailed] = useState(false)
  const resetTimer = useRef<number | null>(null)

  useEffect(
    () => () => {
      if (resetTimer.current !== null) window.clearTimeout(resetTimer.current)
    },
    [],
  )

  const copy = async () => {
    setFailed(false)
    try {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(userId)
      setCopied(true)
      if (resetTimer.current !== null) window.clearTimeout(resetTimer.current)
      resetTimer.current = window.setTimeout(() => {
        setCopied(false)
        resetTimer.current = null
      }, 2000)
    } catch {
      setCopied(false)
      setFailed(true)
    }
  }

  return (
    <span className={styles.copyControl}>
      <IconButton
        icon={copied ? CheckIcon : CopyIcon}
        variant="invisible"
        size="small"
        aria-label={profileCopy.copyUserId}
        onClick={() => void copy()}
      />
      <span aria-live="polite">
        {failed ? profileCopy.copyFailed : copied ? profileCopy.copied : ''}
      </span>
    </span>
  )
}
