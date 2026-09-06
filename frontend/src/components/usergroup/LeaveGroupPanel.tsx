import { Banner, Button, ConfirmationDialog } from '@primer/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import type { UserGroup } from '../../api/types'
import styles from './assets.module.css'

interface Props {
  userGroup: UserGroup
  onLeft: () => void
}

/** 非 Owner 成员的主动退出入口；Owner 需先转让所有权，服务端会拒绝。 */
export function LeaveGroupPanel({ userGroup, onLeft }: Props) {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [failed, setFailed] = useState(false)

  const leave = async () => {
    setSubmitting(true)
    setFailed(false)
    try {
      await api.leaveUserGroup(userGroup.id)
      onLeft()
      navigate('/')
    } catch {
      setFailed(true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className={styles.section} aria-labelledby="user-group-leave-title">
      <header className={styles.sectionHeader}>
        <h2 id="user-group-leave-title" className={styles.sectionTitle}>
          退出 User Group
        </h2>
        <p className={styles.sectionDescription}>
          退出后你将失去这个 User Group 及组内资源的访问权，需要重新受邀才能加入。
        </p>
      </header>

      {failed ? (
        <Banner variant="critical" onDismiss={() => setFailed(false)}>
          <Banner.Title>退出失败。</Banner.Title>
          <Banner.Description>请确认你仍是该组成员后重试。</Banner.Description>
        </Banner>
      ) : null}

      <Button
        variant="danger"
        loading={submitting}
        disabled={submitting}
        onClick={() => setConfirmOpen(true)}
      >
        退出 User Group
      </Button>

      {confirmOpen ? (
        <ConfirmationDialog
          title={`退出 ${userGroup.name}？`}
          confirmButtonContent="退出 User Group"
          confirmButtonType="danger"
          confirmButtonLoading={submitting}
          cancelButtonContent="取消"
          onClose={(gesture) => {
            if (submitting) return
            if (gesture === 'confirm') void leave()
            else setConfirmOpen(false)
          }}
        >
          退出后，你将立刻失去这个 User Group 及组内资源的访问权，需要重新受邀才能加入。
        </ConfirmationDialog>
      ) : null}
    </section>
  )
}
