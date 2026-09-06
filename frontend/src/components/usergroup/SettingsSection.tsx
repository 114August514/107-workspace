import { ActionList, Banner, Button, FormControl, Textarea, TextInput } from '@primer/react'
import { useRef, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import styles from '../project/projectSettingsPanel.module.css'
import { LeaveGroupPanel } from './LeaveGroupPanel'

interface Feedback {
  variant: 'success' | 'critical'
}

export function SettingsSection() {
  const { userGroup, reload, onMembershipChanged, onDelete } =
    useOutletContext<UserGroupOutletContext>()
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
    <div className={styles.layout}>
      <nav className={styles.navigation} aria-label="User Group 设置分区">
        <ActionList>
          <ActionList.LinkItem as={Link} to="?section=general" active>
            常规
          </ActionList.LinkItem>
        </ActionList>
      </nav>
      <div className={styles.content}>
        {canUpdate ? (
          <section className={styles.section} aria-labelledby="user-group-settings-title">
            <h2 id="user-group-settings-title" className={styles.paneTitle}>
              基本信息
            </h2>
            <p className={styles.sectionDescription}>修改 User Group 的名称与说明。</p>

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
              className={styles.form}
              autoComplete="off"
              onSubmit={(event) => {
                event.preventDefault()
                if (!submitting) void submit()
              }}
            >
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
                  rows={4}
                  resize="vertical"
                  name="user-group-description"
                  autoComplete="off"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </FormControl>
              <Button type="submit" variant="primary" loading={submitting} disabled={submitting}>
                保存更改
              </Button>
            </form>
          </section>
        ) : null}

        {onDelete || canLeave ? (
          <section className={styles.section} aria-labelledby="user-group-danger-title">
            <h2 id="user-group-danger-title" className={styles.paneTitle}>
              危险操作
            </h2>
            {onDelete ? (
              <div className={styles.danger}>
                <div>
                  <strong>删除 User Group</strong>
                  <p className={styles.sectionDescription}>
                    删除前会检查组内资源和影响范围。若只想退出，请先转让所有权。
                  </p>
                </div>
                <Button variant="danger" onClick={onDelete}>
                  删除 User Group
                </Button>
              </div>
            ) : (
              <LeaveGroupPanel
                compact
                userGroup={userGroup}
                onLeft={() => {
                  onMembershipChanged?.()
                }}
              />
            )}
          </section>
        ) : null}
      </div>
    </div>
  )
}
