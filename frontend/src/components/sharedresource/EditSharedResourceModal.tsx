import { Dialog, Flash, FormControl, TextInput } from '@primer/react'
import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type { SharedResource } from '../../api/types'
import styles from './formControls.module.css'

interface Props {
  open: boolean
  resource: SharedResource | undefined
  onClose: () => void
  onUpdated: () => void
}

export function EditSharedResourceModal({ open, resource, onClose, onUpdated }: Props) {
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{ variant: 'success' | 'danger'; text: string } | null>(
    null,
  )

  useEffect(() => {
    if (open && resource) {
      setName(resource.name)
      setDescription(resource.description ?? '')
      setNameError('')
      setFeedback(null)
      setSubmitting(false)
    }
  }, [open, resource])

  const handleClose = () => {
    if (!submitting) onClose()
  }

  const handleSubmit = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setNameError('名称不能为空')
      return
    }
    setSubmitting(true)
    setFeedback(null)
    try {
      await api.updateSharedResource(resource!.id, {
        name: trimmed,
        description: description.trim(),
      })
      onUpdated()
      onClose()
    } catch (err) {
      setFeedback({ variant: 'danger', text: (err as Error).message })
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null
  return (
    <Dialog
      onClose={handleClose}
      title="修改共享资源"
      footerButtons={[
        { content: '取消', onClick: handleClose, disabled: submitting, buttonType: 'default' },
        {
          content: submitting ? '保存中…' : '保存修改',
          onClick: handleSubmit,
          buttonType: 'primary',
          disabled: submitting,
        },
      ]}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {feedback && <Flash variant={feedback.variant}>{feedback.text}</Flash>}
        <FormControl required>
          <FormControl.Label>名称</FormControl.Label>
          <TextInput
            value={name}
            onChange={(e) => {
              setName(e.target.value)
              if (nameError) setNameError('')
            }}
            maxLength={128}
          />
          {nameError && (
            <FormControl.Validation variant="error">{nameError}</FormControl.Validation>
          )}
        </FormControl>

        <FormControl>
          <FormControl.Label>说明</FormControl.Label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={4096}
            rows={3}
            className={styles.textarea}
          />
        </FormControl>
      </div>
    </Dialog>
  )
}
