import { Banner, Button, FormControl, TextInput } from '@primer/react'
import { useRef, useState } from 'react'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import type { Home } from '../api/types'
import type { AsyncState as AsyncResource } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { settingsCopy } from './settingsCopy'
import styles from './SettingsPage.module.css'

interface Props {
  home: AsyncResource<Home>
}

export function SettingsPage({ home }: Props) {
  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>{settingsCopy.title}</h1>
        <p className={styles.subtitle}>{settingsCopy.subtitle}</p>
      </header>
      <AsyncState
        loading={home.loading}
        loadingText={settingsCopy.loading}
        error={toAsyncError(home.error)}
        onRetry={home.reload}
      >
        {home.data ? <SettingsForm home={home.data} onSaved={home.reload} /> : null}
      </AsyncState>
    </div>
  )
}

function SettingsForm({ home, onSaved }: { home: Home; onSaved: () => void }) {
  const user = home.user
  const displayNameRef = useRef<HTMLInputElement>(null)
  const usernameRef = useRef<HTMLInputElement>(null)
  const [displayName, setDisplayName] = useState(user.display_name)
  const [username, setUsername] = useState(user.username)
  const [displayNameError, setDisplayNameError] = useState<string | null>(null)
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{
    variant: 'success' | 'critical'
    message: string
  } | null>(null)

  const submit = async () => {
    const nextDisplayName = displayName.trim()
    const nextUsername = username.trim()
    let invalid = false
    if (!nextDisplayName) {
      setDisplayNameError(settingsCopy.displayNameRequired)
      displayNameRef.current?.focus()
      invalid = true
    } else {
      setDisplayNameError(null)
    }
    if (!nextUsername) {
      setUsernameError(settingsCopy.usernameRequired)
      if (!invalid) usernameRef.current?.focus()
      invalid = true
    } else {
      setUsernameError(null)
    }
    if (invalid) return

    setSubmitting(true)
    setFeedback(null)
    try {
      await api.updateProfile({ display_name: nextDisplayName, username: nextUsername })
      setFeedback({ variant: 'success', message: settingsCopy.saved })
      onSaved()
    } catch (error) {
      const view = toAsyncError(error as Error)
      setFeedback({
        variant: 'critical',
        message: view?.message || settingsCopy.saveFailed,
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className={styles.section} aria-labelledby="settings-account-title">
      <h2 id="settings-account-title" className={styles.sectionTitle}>
        {settingsCopy.account}
      </h2>
      {feedback ? (
        <Banner variant={feedback.variant} onDismiss={() => setFeedback(null)}>
          <Banner.Title>{feedback.message}</Banner.Title>
          {feedback.variant === 'critical' ? (
            <Banner.Description>{settingsCopy.saveFailedNext}</Banner.Description>
          ) : null}
        </Banner>
      ) : null}
      <form
        autoComplete="off"
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault()
          if (!submitting) void submit()
        }}
      >
        <FormControl required disabled={submitting}>
          <FormControl.Label>{settingsCopy.displayName}</FormControl.Label>
          <TextInput
            ref={displayNameRef}
            name="display-name"
            block
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
          {displayNameError ? (
            <FormControl.Validation variant="error">{displayNameError}</FormControl.Validation>
          ) : null}
        </FormControl>
        <FormControl required disabled={submitting}>
          <FormControl.Label>{settingsCopy.username}</FormControl.Label>
          <TextInput
            ref={usernameRef}
            name="username"
            block
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <FormControl.Caption>{settingsCopy.usernameCaption}</FormControl.Caption>
          {usernameError ? (
            <FormControl.Validation variant="error">{usernameError}</FormControl.Validation>
          ) : null}
        </FormControl>
        <p className={styles.subtitle}>
          {settingsCopy.email}：{user.email?.trim() ? user.email : settingsCopy.emailMissing}。
          {settingsCopy.emailCaption}
        </p>
        <Button type="submit" variant="primary" loading={submitting} disabled={submitting}>
          {settingsCopy.save}
        </Button>
      </form>
    </section>
  )
}
