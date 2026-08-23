import { Banner, Dialog, FormControl, Stack, Textarea, TextInput } from '@primer/react'
import { useRef, useState } from 'react'

import { api } from '../../api/client'
import type { AsyncErrorView } from '../../api/errors'
import { toAsyncError } from '../../api/errors'
import type { UserGroup } from '../../api/types'

interface Props {
  open: boolean
  onClose: () => void
  /** 创建成功后的回调；调用方决定是跳转还是刷新列表。 */
  onCreated: (userGroup: UserGroup) => void
}

export function CreateUserGroupDialog({ open, onClose, onCreated }: Props) {
  // 表单状态放在内层组件里，随弹窗一起挂载卸载：每次打开都是干净表单
  if (!open) return null
  return <CreateUserGroupForm onClose={onClose} onCreated={onCreated} />
}

function CreateUserGroupForm({ onClose, onCreated }: Omit<Props, 'open'>) {
  const nameInputRef = useRef<HTMLInputElement>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<AsyncErrorView | null>(null)

  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setNameError('请填写 User Group 名称')
      nameInputRef.current?.focus()
      return
    }
    setNameError(null)
    setSubmitting(true)
    setSubmitError(null)
    try {
      const userGroup = await api.createUserGroup(trimmed, description.trim())
      onCreated(userGroup)
      onClose()
    } catch (error) {
      setSubmitError(toAsyncError(error as Error) ?? null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      title="创建 User Group"
      width="large"
      initialFocusRef={nameInputRef}
      onClose={() => {
        if (!submitting) onClose()
      }}
      footerButtons={[
        { content: '取消', disabled: submitting, onClick: onClose },
        {
          content: '创建',
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
            <Banner variant="critical" data-testid="create-user-group-error">
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
          <FormControl required disabled={submitting} id="create-user-group-name">
            <FormControl.Label>名称</FormControl.Label>
            <TextInput
              ref={nameInputRef}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：计算物理课题组"
              maxLength={128}
              block
            />
            {nameError && (
              <FormControl.Validation variant="error">{nameError}</FormControl.Validation>
            )}
          </FormControl>
          <FormControl disabled={submitting} id="create-user-group-description">
            <FormControl.Label>说明（可选）</FormControl.Label>
            <Textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="例如：用于计算物理课题组的课程项目"
              maxLength={500}
              rows={4}
              block
              resize="vertical"
            />
            <FormControl.Caption>
              简要写明这个 User Group 用于哪些 Project 或协作任务。
            </FormControl.Caption>
          </FormControl>
        </Stack>
      </form>
    </Dialog>
  )
}
