import { CopyIcon, PencilIcon, PlusIcon, TrashIcon } from '@primer/octicons-react'
import {
  Button,
  ConfirmationDialog,
  Dialog,
  Flash,
  FormControl,
  IconButton,
  RelativeTime,
  Stack,
  Textarea,
  TextInput,
  VisuallyHidden,
} from '@primer/react'
import { useState } from 'react'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { Project, Variable } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncSection } from '../common/AsyncSection'
import styles from './projectSettingsPanel.module.css'

interface Props {
  projectId: string
  access: Project | undefined
  onChanged?: () => void
}

type VariableDialog = { mode: 'create' } | { mode: 'edit'; name: string; value: string } | null

/**
 * Project Variable 管理（Issue #54）。
 *
 * 自包含面板：只依赖 projectId 与 access，Settings 表面直接挂载。
 * 列表与弹窗样式对齐 #94 Project 页；解析语义由后端 contract 决定，
 * 前端只做 CRUD 入口。
 */
export function ProjectVariablesPanel({ projectId, access, onChanged }: Props) {
  const canManage = can(access, 'config.manage')
  const variables = useAsync<Variable[]>(() => api.listProjectVariables(projectId), [projectId])
  const [dialog, setDialog] = useState<VariableDialog>(null)
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)
  const [valueError, setValueError] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)

  const openCreate = () => {
    setName('')
    setValue('')
    setDialog({ mode: 'create' })
  }

  const openEdit = (row: Variable) => {
    setName(row.name)
    setValue(row.value)
    setDialog({ mode: 'edit', name: row.name, value: row.value })
  }

  const closeDialog = () => {
    setDialog(null)
    setNameError(null)
    setValueError(null)
    setApiError(null)
  }

  const submit = async () => {
    let nextNameError: string | null = null
    if (!name) {
      nextNameError = '请输入名称'
    } else if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) {
      nextNameError = '只能包含字母、数字和下划线，且不能以数字开头'
    }
    const nextValueError = value ? null : '请输入值'
    setNameError(nextNameError)
    setValueError(nextValueError)
    if (nextNameError || nextValueError) return

    try {
      await api.putProjectVariable(projectId, { name, value })
      setApiError(null)
      setDialog(null)
      variables.reload()
      onChanged?.()
    } catch (error) {
      setApiError((error as Error).message)
    }
  }

  const remove = async (target: string) => {
    try {
      await api.deleteProjectVariable(projectId, target)
      setListError(null)
      variables.reload()
      onChanged?.()
    } catch (error) {
      setListError((error as Error).message)
    }
  }

  const rows = variables.data ?? []

  return (
    <section id="settings-pane" className={styles.section} aria-label="Project variables">
      <div className={styles.paneHeader}>
        <h2 className={styles.paneTitle}>Project variables</h2>
        {canManage && (
          <Button variant="primary" leadingVisual={PlusIcon} onClick={openCreate}>
            新建 Variable
          </Button>
        )}
      </div>
      <p className={styles.sectionDescription}>
        在运行方案的环境变量里用 <code className={styles.reference}>{'${{ vars.NAME }}'}</code>{' '}
        引用；引用按 Project → Project Owner 顺序解析，结果由后端确认。
      </p>

      {listError && <Flash variant="danger">{listError}</Flash>}

      <AsyncSection
        loading={variables.loading}
        error={variables.error}
        errorTitle="Variable 加载失败"
      >
        {rows.length === 0 ? (
          <p className={styles.empty}>
            还没有 Project Variable。创建后可以在运行方案环境变量中引用。
          </p>
        ) : (
          <table className={styles.list}>
            <colgroup>
              <col className={styles.colName} />
              <col className={styles.colValue} />
              <col className={styles.colUpdated} />
              {canManage && <col className={styles.colActions} />}
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className={styles.th}>
                  名称
                </th>
                <th scope="col" className={styles.th}>
                  值
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
              {rows.map((variable) => (
                <tr key={variable.name} className={styles.row}>
                  <td className={styles.td}>{variable.name}</td>
                  <td className={styles.td}>
                    <span className={styles.valueInner}>
                      <span className={styles.valueText}>{variable.value}</span>
                      <IconButton
                        size="small"
                        variant="invisible"
                        icon={CopyIcon}
                        aria-label={`复制 ${variable.name} 的值`}
                        onClick={() => void navigator.clipboard?.writeText(variable.value)}
                      />
                    </span>
                  </td>
                  <td className={`${styles.td} ${styles.time}`}>
                    <RelativeTime datetime={variable.updated_at} />
                  </td>
                  {canManage && (
                    <td className={`${styles.td} ${styles.iconCell}`}>
                      <IconButton
                        variant="invisible"
                        icon={PencilIcon}
                        aria-label={`编辑 ${variable.name}`}
                        onClick={() => openEdit(variable)}
                      />
                      <IconButton
                        variant="invisible"
                        icon={TrashIcon}
                        aria-label={`删除 ${variable.name}`}
                        onClick={() => setPendingDelete(variable.name)}
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
          onClose={closeDialog}
          title={dialog.mode === 'edit' ? `编辑 Variable「${dialog.name}」` : '新建 Variable'}
          width="medium"
          footerButtons={[
            { content: '取消', onClick: closeDialog, buttonType: 'default' },
            { content: '保存', onClick: () => void submit(), buttonType: 'primary' },
          ]}
        >
          <Stack direction="vertical" gap="normal">
            {apiError && <Flash variant="danger">{apiError}</Flash>}
            <FormControl required disabled={dialog.mode === 'edit'}>
              <FormControl.Label>名称</FormControl.Label>
              <TextInput
                block
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如 DATASET_URL"
              />
              {nameError ? (
                <FormControl.Validation variant="error">{nameError}</FormControl.Validation>
              ) : (
                <FormControl.Caption>
                  字母、数字和下划线，不能以数字开头；保存后名称不可修改。
                </FormControl.Caption>
              )}
            </FormControl>
            <FormControl required>
              <FormControl.Label>值</FormControl.Label>
              <Textarea
                block
                className={styles.textarea}
                rows={3}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="可以是字面量"
              />
              {valueError && (
                <FormControl.Validation variant="error">{valueError}</FormControl.Validation>
              )}
            </FormControl>
          </Stack>
        </Dialog>
      )}

      {pendingDelete && (
        <ConfirmationDialog
          title={`删除 Variable「${pendingDelete}」？`}
          cancelButtonContent="取消"
          confirmButtonContent="删除"
          confirmButtonType="danger"
          onClose={(gesture) => {
            const target = pendingDelete
            setPendingDelete(null)
            if (gesture === 'confirm' && target) void remove(target)
          }}
        >
          引用它的运行方案会在保存时因解析失败而报错，已有 Run 不受影响。
        </ConfirmationDialog>
      )}
    </section>
  )
}
