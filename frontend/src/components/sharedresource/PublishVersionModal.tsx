import { CloudIcon } from '@primer/octicons-react'
import { Dialog, Flash, FormControl, Stack, TextInput } from '@primer/react'
import { type DragEvent, useCallback, useEffect, useId, useState } from 'react'

import { api } from '../../api/client'
import type { SharedResourceVersion } from '../../api/types'
import styles from './publishVersion.module.css'

interface Props {
  open: boolean
  resourceId: string
  onClose: () => void
  onPublished: (version: SharedResourceVersion) => void
}

/**
 * 文件拖拽上传区域。
 *
 * 替代 antd Upload.Dragger：用原生 input + drag 事件实现，样式对齐 Primer token。
 * 可访问性：整个区域是 <label>，关联隐藏的 file input——键盘 Tab 到 input 能聚焦，
 * 回车/空格触发选择；聚焦时 dropArea 通过 :focus-within 高亮，焦点可见。
 */
function DropArea({
  files,
  onAdd,
  onRemove,
}: {
  files: File[]
  onAdd: (file: File) => void
  onRemove: (file: File) => void
}) {
  const [dragging, setDragging] = useState(false)
  const inputId = useId()

  const handleDrop = useCallback(
    (e: DragEvent<HTMLLabelElement>) => {
      e.preventDefault()
      setDragging(false)
      for (const file of e.dataTransfer?.files ?? []) {
        onAdd(file)
      }
    },
    [onAdd],
  )

  const handleDragOver = useCallback((e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault()
    setDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLLabelElement>) => {
    // 只在真正离开区域时取消高亮
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragging(false)
    }
  }, [])

  return (
    <div>
      <label
        className={styles.dropArea}
        data-dragging={dragging}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          id={inputId}
          className={styles.fileInput}
          aria-label="文件"
          type="file"
          multiple
          onChange={(e) => {
            for (const file of e.target.files ?? []) {
              onAdd(file)
            }
            // 允许重复选同一个文件
            e.target.value = ''
          }}
        />
        <CloudIcon size={24} />
        <p className={styles.dropTitle}>点击或拖拽文件到此处</p>
        <p className={styles.dropHint}>
          支持多选。同名路径会导致版本发布失败，必要时用下面的前缀区分。
        </p>
      </label>
      {files.length > 0 && (
        <ul className={styles.fileList}>
          {files.map((file, idx) => (
            <li key={`${file.name}-${idx}`} className={styles.fileItem}>
              <code className={styles.fileName}>{file.name}</code>
              <button
                type="button"
                className={styles.removeButton}
                onClick={() => onRemove(file)}
                aria-label={`移除 ${file.name}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function PublishVersionModal(props: Props) {
  return <ResourcePublishVersionModal key={props.resourceId} {...props} />
}

function ResourcePublishVersionModal({ open, resourceId, onClose, onPublished }: Props) {
  const attemptStorageKey = `shared-resource-publication-attempt:${resourceId}`
  const [files, setFiles] = useState<File[]>([])
  const [prefix, setPrefix] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [polling, setPolling] = useState(false)
  const [attemptId, setAttemptId] = useState<string | null>(() =>
    window.sessionStorage.getItem(attemptStorageKey),
  )
  const [feedback, setFeedback] = useState<{ variant: 'success' | 'danger'; text: string } | null>(
    null,
  )

  useEffect(() => {
    if (!open || !polling || attemptId === null) return

    const controller = new AbortController()
    let timer: number | undefined

    const poll = async () => {
      try {
        const attempt = await api.getSharedResourcePublicationAttempt(attemptId, controller.signal)
        if (controller.signal.aborted) return

        if (attempt.status === 'failed') {
          window.sessionStorage.removeItem(attemptStorageKey)
          setAttemptId(null)
          setPolling(false)
          setFeedback({
            variant: 'danger',
            text: attempt.failure_reason ?? attempt.validation_summary,
          })
          return
        }
        if (attempt.status === 'succeeded' && attempt.version_id !== null) {
          const version = await api.getSharedResourceVersion(attempt.version_id, controller.signal)
          if (controller.signal.aborted) return
          window.sessionStorage.removeItem(attemptStorageKey)
          setFiles([])
          setPrefix('')
          setDescription('')
          setFeedback(null)
          setAttemptId(null)
          setPolling(false)
          onPublished(version)
          return
        }

        setFeedback({ variant: 'success', text: attempt.validation_summary })
        timer = window.setTimeout(() => void poll(), 500)
      } catch (err) {
        if (controller.signal.aborted) return
        setPolling(false)
        setFeedback({ variant: 'danger', text: (err as Error).message })
      }
    }

    void poll()
    return () => {
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [attemptId, attemptStorageKey, onPublished, open, polling])

  const handleClose = () => {
    if (submitting) return
    setPolling(false)
    if (attemptId !== null) {
      setFeedback({ variant: 'success', text: '已暂停查询；可重新打开并继续查询结果' })
    }
    onClose()
  }

  const handleSubmit = async () => {
    if (attemptId !== null) {
      setFeedback({ variant: 'success', text: '正在查询校验结果…' })
      setPolling(true)
      return
    }
    if (files.length === 0) {
      setFeedback({ variant: 'danger', text: '请至少选择一个文件' })
      return
    }

    setSubmitting(true)
    setFeedback(null)
    try {
      const attempt = await api.createSharedResourcePublicationAttempt(resourceId, {
        files,
        description: description.trim(),
        prefix: prefix.trim() || undefined,
      })
      window.sessionStorage.setItem(attemptStorageKey, attempt.id)
      setAttemptId(attempt.id)
      setFeedback({ variant: 'success', text: attempt.validation_summary })
      setPolling(true)
    } catch (err) {
      setFeedback({ variant: 'danger', text: (err as Error).message })
    } finally {
      setSubmitting(false)
    }
  }

  const addFile = useCallback((file: File) => {
    setFiles((prev) => [...prev, file])
  }, [])

  const removeFile = useCallback((file: File) => {
    setFiles((prev) => prev.filter((f) => f !== file))
  }, [])

  if (!open) return null
  return (
    <Dialog
      onClose={handleClose}
      title="发布版本"
      width="medium"
      footerButtons={[
        { content: '取消', onClick: handleClose, disabled: submitting, buttonType: 'default' },
        {
          content: submitting
            ? '正在上传…'
            : polling
              ? '正在校验…'
              : attemptId
                ? '继续查询结果'
                : '发布版本',
          onClick: handleSubmit,
          buttonType: 'primary',
          disabled: submitting || polling,
        },
      ]}
    >
      <Stack direction="vertical" gap="normal">
        {feedback && <Flash variant={feedback.variant}>{feedback.text}</Flash>}

        <FormControl required>
          <FormControl.Label>文件</FormControl.Label>
          <DropArea files={files} onAdd={addFile} onRemove={removeFile} />
        </FormControl>

        <FormControl>
          <FormControl.Label>路径前缀</FormControl.Label>
          <TextInput
            value={prefix}
            onChange={(e) => setPrefix(e.target.value)}
            placeholder="例如：data/"
            maxLength={128}
          />
          <FormControl.Caption>可选。文件会写入 prefix/文件名。</FormControl.Caption>
        </FormControl>

        <FormControl>
          <FormControl.Label>版本说明</FormControl.Label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={4096}
            rows={3}
            className={styles.textarea}
          />
        </FormControl>
      </Stack>
    </Dialog>
  )
}
