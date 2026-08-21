import { Dialog, Flash, FormControl, Stack, TextInput } from '@primer/react'
import { useState } from 'react'

import { api } from '../../api/client'
import type { SharedResource } from '../../api/types'
import styles from './formControls.module.css'

interface Props {
  open: boolean
  workspaceId: string
  onClose: () => void
  onCreated: (resource: SharedResource) => void
}

export function CreateSharedResourceModal({ open, workspaceId, onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{ variant: 'success' | 'danger'; text: string } | null>(
    null,
  )

  const reset = () => {
    setName('')
    setNameError('')
    setDescription('')
    setFeedback(null)
    setSubmitting(false)
  }

  const handleClose = () => {
    if (!submitting) {
      reset()
      onClose()
    }
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
      const resource = await api.createSharedResource(workspaceId, trimmed, description.trim())
      reset()
      onCreated(resource)
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
      title="创建共享资源"
      footerButtons={[
        { content: '取消', onClick: handleClose, disabled: submitting, buttonType: 'default' },
        {
          content: submitting ? '创建中…' : '创建共享资源',
          onClick: handleSubmit,
          buttonType: 'primary',
          disabled: submitting,
        },
      ]}
    >
      <Stack direction="vertical" gap="normal">
        {feedback && <Flash variant={feedback.variant}>{feedback.text}</Flash>}
        <FormControl required>
          <FormControl.Label>名称</FormControl.Label>
          <TextInput
            value={name}
            onChange={(e) => {
              setName(e.target.value)
              if (nameError) setNameError('')
            }}
            placeholder="例如：预训练权重"
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
            placeholder="（选填）"
            maxLength={4096}
            rows={3}
            className={styles.textarea}
          />
        </FormControl>
      </Stack>
    </Dialog>
  )
}
