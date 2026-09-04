import { LockIcon, PencilIcon, PlusIcon, TrashIcon } from '@primer/octicons-react'
import {
  Banner,
  Button,
  ConfirmationDialog,
  Dialog,
  FormControl,
  IconButton,
  RelativeTime,
  Stack,
  TextInput,
  VisuallyHidden,
} from '@primer/react'
import { useRef, useState } from 'react'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import type { AsyncErrorView } from '../../api/errors'
import { can } from '../../api/types'
import type { Project, Secret } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncSection } from '../common/AsyncSection'
import styles from './projectSettingsPanel.module.css'

interface Props {
  projectId: string
  access: Project | undefined
  onChanged?: () => void
}

type SecretDialog = { mode: 'create' } | { mode: 'replace'; name: string } | null

/**
 * Project Secret 管理（Issue #54）。
 *
 * Secret 只能写入和轮换，不能回读：列表只展示名字与更新时间，
 * 表单值输入后即提交，不在前端保存或回显明文。
 * 弹窗结构与 CreateUserGroupDialog 一致。
 */
export function ProjectSecretsPanel({ projectId, access, onChanged }: Props) {
  const canManage = can(access, 'config.manage')
  const secrets = useAsync<Secret[]>(() => api.listProjectSecrets(projectId), [projectId])
  const [dialog, setDialog] = useState<SecretDialog>(null)
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)
  const [valueError, setValueError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<AsyncErrorView | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [listError, setListError] = useState<AsyncErrorView | null>(null)
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const nameInputRef = useRef<HTMLInputElement>(null)
  const valueInputRef = useRef<HTMLInputElement>(null)

  const openCreate = () => {
    setName('')
    setValue('')
    setDialog({ mode: 'create' })
  }

  const openReplace = (target: string) => {
    setName(target)
    setValue('')
    setDialog({ mode: 'replace', name: target })
  }

  const closeDialog = () => {
    setDialog(null)
    setNameError(null)
    setValueError(null)
    setSubmitError(null)
  }

  const submit = async () => {
    const trimmed = name.trim()
    let nextNameError: string | null = null
    if (!trimmed) {
      nextNameError = '请输入名称'
    } else if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(trimmed)) {
      nextNameError = '只能包含字母、数字和下划线，且不能以数字开头'
    }
    const nextValueError = value ? null : '请输入值；保存后不能回读'
    setNameError(nextNameError)
    setValueError(nextValueError)
    if (nextNameError || nextValueError) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      await api.putProjectSecret(projectId, { name: trimmed, value })
      setDialog(null)
      secrets.reload()
      onChanged?.()
    } catch (error) {
      setSubmitError(toAsyncError(error as Error) ?? null)
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (target: string) => {
    try {
      await api.deleteProjectSecret(projectId, target)
      setListError(null)
      secrets.reload()
      onChanged?.()
    } catch (error) {
      setListError(toAsyncError(error as Error) ?? null)
    }
  }

  const rows = secrets.data ?? []

  return (
    <section id="settings-pane" className={styles.section} aria-label="Project secrets">
      <div className={styles.paneHeader}>
        <h2 className={styles.paneTitle}>Project secrets</h2>
        {canManage && (
          <Button variant="primary" leadingVisual={PlusIcon} onClick={openCreate}>
            新建 Secret
          </Button>
        )}
      </div>
      <p className={styles.sectionDescription}>
        在运行方案环境变量里用 <code className={styles.reference}>{'${{ secrets.NAME }}'}</code>{' '}
        引用；值只在写入时可见，保存后不能回读，列表只展示名字。
      </p>

      {listError && (
        <Banner variant="critical">
          <Banner.Title>{listError.message}</Banner.Title>
        </Banner>
      )}

      <AsyncSection loading={secrets.loading} error={secrets.error} errorTitle="Secret 加载失败">
        {rows.length === 0 ? (
          <p className={styles.empty}>
            还没有 Project Secret。创建后可以在运行方案环境变量中引用。
          </p>
        ) : (
          <table className={styles.list}>
            <colgroup>
              <col className={styles.colNameWide} />
              <col className={styles.colUpdated} />
              {canManage && <col className={styles.colActions} />}
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className={styles.th}>
                  名称
                </th>
                <th scope="col" className={styles.th}>
                  最近更新
                </th>
                {canManage && (
                  <th scope="col" className={styles.th}>
                    <VisuallyHidden>操作</VisuallyHidden>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((secret) => (
                <tr key={secret.name} className={styles.row}>
                  <td className={styles.td}>
                    <LockIcon size={16} className={styles.lockIcon} />
                    {secret.name}
                  </td>
                  <td className={`${styles.td} ${styles.time}`}>
                    <RelativeTime datetime={secret.updated_at} />
                  </td>
                  {canManage && (
                    <td className={`${styles.td} ${styles.iconCell}`}>
                      <IconButton
                        variant="invisible"
                        icon={PencilIcon}
                        aria-label={`替换 ${secret.name} 的值`}
                        onClick={() => openReplace(secret.name)}
                      />
                      <IconButton
                        variant="invisible"
                        icon={TrashIcon}
                        aria-label={`删除 ${secret.name}`}
                        onClick={() => setPendingDelete(secret.name)}
                      />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </AsyncSection>

      {dialog && (
        <Dialog
          onClose={() => {
            if (!submitting) closeDialog()
          }}
          initialFocusRef={dialog.mode === 'replace' ? valueInputRef : nameInputRef}
          title={dialog.mode === 'replace' ? `替换 Secret「${dialog.name}」的值` : '新建 Secret'}
          width="medium"
          footerButtons={[
            { content: '取消', disabled: submitting, onClick: closeDialog },
            {
              content: '保存',
              buttonType: 'primary',
              loading: submitting,
              disabled: submitting,
              onClick: () => void submit(),
            },
          ]}
        >
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (!submitting) void submit()
            }}
          >
            <Stack gap="normal">
              {submitError && (
                <Banner variant="critical">
                  <Banner.Title>{submitError.message}</Banner.Title>
                  {submitError.problems && submitError.problems.length > 0 && (
                    <Banner.Description>
                      <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                        {submitError.problems.map((problem) => (
                          <li key={problem}>{problem}</li>
                        ))}
                      </ul>
                    </Banner.Description>
                  )}
                </Banner>
              )}
              <FormControl required disabled={dialog.mode === 'replace'} id="project-secret-name">
                <FormControl.Label>名称</FormControl.Label>
                <TextInput
                  ref={nameInputRef}
                  block
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="例如 HF_TOKEN"
                  maxLength={128}
                />
                {nameError ? (
                  <FormControl.Validation variant="error">{nameError}</FormControl.Validation>
                ) : (
                  <FormControl.Caption>字母、数字和下划线，不能以数字开头。</FormControl.Caption>
                )}
              </FormControl>
              <FormControl required disabled={submitting} id="project-secret-value">
                <FormControl.Label>{dialog.mode === 'replace' ? '新值' : '值'}</FormControl.Label>
                <TextInput
                  ref={valueInputRef}
                  block
                  type="password"
                  autoComplete="new-password"
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                  placeholder={dialog.mode === 'replace' ? '输入替换后的值' : 'Secret 的值'}
                />
                {valueError ? (
                  <FormControl.Validation variant="error">{valueError}</FormControl.Validation>
                ) : (
                  <FormControl.Caption>
                    值只在写入时可见；引用它的 Run 在 Preflight 中明确失败，不会被替换为空值。
                  </FormControl.Caption>
                )}
              </FormControl>
            </Stack>
          </form>
        </Dialog>
      )}

      {pendingDelete && (
        <ConfirmationDialog
          title={`删除 Secret「${pendingDelete}」？`}
          cancelButtonContent="取消"
          confirmButtonContent="删除"
          confirmButtonType="danger"
          onClose={(gesture) => {
            const target = pendingDelete
            setPendingDelete(null)
            if (gesture === 'confirm' && target) void remove(target)
          }}
        >
          引用它的 Run 会在 Preflight 中明确失败，不会被替换为空值；已有 Run 不受影响。
        </ConfirmationDialog>
      )}
    </section>
  )
}
