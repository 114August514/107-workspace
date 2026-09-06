import { KebabHorizontalIcon } from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Banner,
  ConfirmationDialog,
  Dialog,
  FormControl,
  IconButton,
  Stack,
  TextInput,
} from '@primer/react'
import { useState } from 'react'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'

interface Props {
  projectId: string
  path: string
  canWrite: boolean
  onChanged: () => void
}

type EditMode = 'rename' | 'copy' | null

export function FileObjectActions({ projectId, path, canWrite, onChanged }: Props) {
  const [editMode, setEditMode] = useState<EditMode>(null)
  const [targetPath, setTargetPath] = useState(path)
  const [saving, setSaving] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!canWrite) return null

  const openEdit = (mode: Exclude<EditMode, null>) => {
    setError(null)
    setTargetPath(mode === 'copy' ? `${path}-copy` : path)
    setEditMode(mode)
  }

  const saveEdit = async () => {
    const destination = targetPath.trim()
    if (!destination) {
      setError('请填写目标路径。')
      return
    }
    setSaving(true)
    setError(null)
    try {
      if (editMode === 'rename') await api.movePath(projectId, path, destination)
      if (editMode === 'copy') await api.copyPath(projectId, path, destination)
      setEditMode(null)
      onChanged()
    } catch (cause) {
      setError(toAsyncError(cause as Error)?.problems?.join(' ') ?? '操作失败，请重试。')
    } finally {
      setSaving(false)
    }
  }
  const download = async () => {
    try {
      await api.downloadFile(projectId, path)
    } catch (cause) {
      setError(toAsyncError(cause as Error)?.problems?.join(' ') ?? '下载失败，请重试。')
    }
  }

  const remove = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.deletePath(projectId, path)
      setDeleteOpen(false)
      onChanged()
    } catch (cause) {
      setError(toAsyncError(cause as Error)?.problems?.join(' ') ?? '删除失败，请重试。')
      setDeleteOpen(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <ActionMenu>
        <ActionMenu.Anchor>
          <IconButton
            icon={KebabHorizontalIcon}
            variant="invisible"
            size="small"
            aria-label={`更多文件操作 ${path}`}
          />
        </ActionMenu.Anchor>
        <ActionMenu.Overlay align="end" width="auto">
          <ActionList>
            <ActionList.Item onSelect={() => void download()}>下载文件</ActionList.Item>
            <ActionList.Divider />
            <ActionList.Item onSelect={() => openEdit('rename')}>重命名</ActionList.Item>
            <ActionList.Item onSelect={() => openEdit('copy')}>复制</ActionList.Item>
            <ActionList.Item variant="danger" onSelect={() => setDeleteOpen(true)}>
              删除
            </ActionList.Item>
          </ActionList>
        </ActionMenu.Overlay>
      </ActionMenu>

      {editMode && (
        <Dialog
          title={editMode === 'rename' ? '重命名文件' : '复制文件'}
          onClose={() => setEditMode(null)}
          footerButtons={[
            { content: '取消', onClick: () => setEditMode(null), disabled: saving },
            {
              content: editMode === 'rename' ? '重命名' : '复制',
              buttonType: 'primary',
              loading: saving,
              disabled: saving,
              onClick: () => void saveEdit(),
            },
          ]}
        >
          <Stack gap="normal">
            {error && (
              <Banner variant="critical">
                <Banner.Title>{error}</Banner.Title>
              </Banner>
            )}
            <FormControl required>
              <FormControl.Label>目标路径</FormControl.Label>
              <TextInput
                value={targetPath}
                onChange={(event) => setTargetPath(event.target.value)}
                block
              />
            </FormControl>
          </Stack>
        </Dialog>
      )}

      {deleteOpen && (
        <ConfirmationDialog
          title={`删除文件“${path}”？`}
          onClose={(gesture) => {
            if (gesture === 'confirm') void remove()
            else setDeleteOpen(false)
          }}
          confirmButtonContent="删除文件"
          confirmButtonType="danger"
          confirmButtonLoading={saving}
        >
          {error ? (
            <Banner variant="critical">{error}</Banner>
          ) : (
            '删除后无法从 Working State 恢复。'
          )}
        </ConfirmationDialog>
      )}
    </>
  )
}
