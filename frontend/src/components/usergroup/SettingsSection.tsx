import { Banner, Button, FormControl, Textarea, TextInput } from '@primer/react'
import { useRef, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import styles from './assets.module.css'
import { LeaveGroupPanel } from './LeaveGroupPanel'

interface Feedback {
  variant: 'success' | 'critical'
}

export function SettingsSection() {
  const { userGroup, reload, onMembershipChanged } = useOutletContext<UserGroupOutletContext>()
  const canUpdate = can(userGroup, 'user_group.update')
  const canLeave = userGroup.role !== 'owner'
  const nameRef = useRef<HTMLInputElement>(null)
  const [name, setName] = useState(userGroup.name)
  const [description, setDescription] = useState(userGroup.description)
  const [nameError, setNameError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<Feedback | null>(null)

  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setNameError('名称不能为空')
      nameRef.current?.focus()
      return
    }
    setNameError(null)
    setSubmitting(true)
    setFeedback(null)
    try {
      await api.updateUserGroup(userGroup.id, {
        name: trimmed,
        description: description.trim(),
      })
      setFeedback({ variant: 'success' })
      reload()
    } catch {
      setFeedback({ variant: 'critical' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.membersSection}>
      {canUpdate ? (
        <section className={styles.section} aria-labelledby="user-group-settings-title">
          <header className={styles.sectionHeader}>
            <h2 id="user-group-settings-title" className={styles.sectionTitle}>
              设置
            </h2>
            <p className={styles.sectionDescription}>修改 User Group 的名称与说明。</p>
          </header>

          {feedback ? (
            <Banner variant={feedback.variant} onDismiss={() => setFeedback(null)}>
              <Banner.Title>
                {feedback.variant === 'success' ? 'User Group 设置已保存。' : '保存失败。'}
              </Banner.Title>
              {feedback.variant === 'critical' ? (
                <Banner.Description>请确认你仍有管理权限后重试。</Banner.Description>
              ) : null}
            </Banner>
          ) : null}

          <form
            autoComplete="off"
            onSubmit={(event) => {
              event.preventDefault()
              if (!submitting) void submit()
            }}
          >
            <div className={styles.settingsForm}>
              <FormControl required disabled={submitting} id="user-group-name">
                <FormControl.Label>名称</FormControl.Label>
                <TextInput
                  ref={nameRef}
                  block
                  name="user-group-name"
                  autoComplete="off"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
                {nameError ? (
                  <FormControl.Validation variant="error">{nameError}</FormControl.Validation>
                ) : null}
              </FormControl>
              <FormControl disabled={submitting} id="user-group-description">
                <FormControl.Label>说明</FormControl.Label>
                <Textarea
                  block
                  name="user-group-description"
                  autoComplete="off"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
                <FormControl.Caption>说明会显示在 User Group 的 About 中。</FormControl.Caption>
              </FormControl>
              <Button type="submit" variant="primary" loading={submitting} disabled={submitting}>
                保存设置
              </Button>
            </div>
          </form>
        </section>
      ) : null}

      {canLeave ? (
        <LeaveGroupPanel
          userGroup={userGroup}
          onLeft={() => {
            onMembershipChanged?.()
          }}
        />
      ) : null}
    </div>
  )
}
