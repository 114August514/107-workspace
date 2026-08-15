import { CloudIcon } from '@primer/octicons-react'
import { Dialog, Flash, FormControl, TextInput } from '@primer/react'
import { type DragEvent, useCallback, useId, useState } from 'react'

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

export function PublishVersionModal({ open, resourceId, onClose, onPublished }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [prefix, setPrefix] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{ variant: 'success' | 'danger'; text: string } | null>(
    null,
  )

  const reset = () => {
    setFiles([])
    setPrefix('')
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
    if (files.length === 0) {
      setFeedback({ variant: 'danger', text: '请至少选择一个文件' })
      return
    }
    setSubmitting(true)
    setFeedback(null)
    try {
      const version = await api.publishSharedResourceVersion(resourceId, {
        files,
        description: description.trim(),
        prefix: prefix.trim() || undefined,
      })
      reset()
      onPublished(version)
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
          content: submitting ? '发布中…' : '发布版本',
          onClick: handleSubmit,
          buttonType: 'primary',
          disabled: submitting,
        },
      ]}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
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
      </div>
    </Dialog>
  )
}
