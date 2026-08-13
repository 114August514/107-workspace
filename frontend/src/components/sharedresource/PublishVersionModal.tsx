import { CloudIcon } from '@primer/octicons-react'
import { Dialog, Flash, FormControl, TextInput } from '@primer/react'
import { type DragEvent, useCallback, useState } from 'react'

import { api } from '../../api/client'
import type { SharedResourceVersion } from '../../api/types'

interface Props {
  open: boolean
  resourceId: string
  onClose: () => void
  onPublished: (version: SharedResourceVersion) => void
}

/**
 * 文件拖拽上传区域。
 *
 * 替代 antd Upload.Dragger：用原生 input + drag 事件实现，样式对齐 Primer 的
 * 边框和间距 token，上传逻辑仍走 FormData 以保持 X-User 头与契约兼容。
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

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragging(false)
      for (const file of e.dataTransfer?.files ?? []) {
        onAdd(file)
      }
    },
    [onAdd],
  )

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    // 只在真正离开区域时取消高亮
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragging(false)
    }
  }, [])

  return (
    <div>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        style={{
          border: `2px dashed ${dragging ? 'var(--fgColor-accent)' : 'var(--borderColor-default)'}`,
          borderRadius: 6,
          padding: '24px 16px',
          textAlign: 'center',
          backgroundColor: dragging ? 'var(--bgColor-accent-muted)' : 'var(--bgColor-muted)',
          transition: 'border-color 0.15s, background-color 0.15s',
          cursor: 'pointer',
        }}
        onClick={() => document.getElementById('publish-file-input')?.click()}
      >
        <CloudIcon size={24} />
        <div style={{ marginTop: 8, fontSize: 14 }}>点击或拖拽文件到此处</div>
        <div style={{ marginTop: 4, fontSize: 12, color: 'var(--fgColor-muted)' }}>
          支持多选。同名路径会导致版本发布失败，必要时用下面的前缀区分。
        </div>
      </div>
      <input
        id="publish-file-input"
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => {
          for (const file of e.target.files ?? []) {
            onAdd(file)
          }
          // 允许重复选同一个文件
          e.target.value = ''
        }}
      />
      {files.length > 0 && (
        <ul style={{ margin: '12px 0 0 0', padding: 0, listStyle: 'none' }}>
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '4px 0',
                fontSize: 13,
              }}
            >
              <code style={{ fontFamily: 'var(--fontFamily-mono)' }}>{file.name}</code>
              <button
                type="button"
                onClick={() => onRemove(file)}
                style={{
                  border: 'none',
                  background: 'none',
                  cursor: 'pointer',
                  color: 'var(--fgColor-muted)',
                  fontSize: 16,
                  padding: '0 4px',
                }}
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
      title="发布新版本"
      width="medium"
      footerButtons={[
        { content: '取消', onClick: handleClose, disabled: submitting, buttonType: 'default' },
        {
          content: submitting ? '发布中…' : '发布',
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
            style={{
              width: '100%',
              padding: '8px 12px',
              fontSize: 14,
              lineHeight: 1.5,
              border: '1px solid var(--borderColor-default)',
              borderRadius: 6,
              resize: 'vertical',
              fontFamily: 'inherit',
            }}
          />
        </FormControl>
      </div>
    </Dialog>
  )
}
