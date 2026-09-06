import { Banner, Button, FormControl, Select, Stack, Textarea, TextInput } from '@primer/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError, type AsyncErrorView } from '../api/errors'
import type { Home, OwnerReference } from '../api/types'
import type { AsyncState as AsyncResource } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'

export function CreateProjectPage({ home }: { home: AsyncResource<Home> }) {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [ownerKey, setOwnerKey] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<AsyncErrorView | null>(null)

  const user = home.data?.user
  const ownerOptions: Array<{ key: string; label: string; owner: OwnerReference }> = user
    ? [
        {
          key: `user:${user.id}`,
          label: `${user.display_name}（个人）`,
          owner: { kind: 'user', id: user.id },
        },
        ...(home.data?.user_groups ?? [])
          .filter((group) => group.role === 'owner')
          .map((group) => ({
            key: `user_group:${group.id}`,
            label: group.name,
            owner: { kind: 'user_group' as const, id: group.id },
          })),
      ]
    : []
  const selectedOwner = ownerOptions.find((option) => option.key === ownerKey) ?? ownerOptions[0]

  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed || !selectedOwner) {
      setError({ message: '请填写 Project 名称并选择 Owner。', problems: [] })
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const project = await api.createProject({
        owner: selectedOwner.owner,
        name: trimmed,
        description: description.trim(),
      })
      navigate(`/projects/${project.id}/files`)
    } catch (cause) {
      setError(toAsyncError(cause as Error) ?? { message: '无法创建 Project。', problems: [] })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AsyncState
      loading={home.loading}
      loadingText="正在加载可用 Owner…"
      error={home.error ? { message: '无法加载可用 Owner。' } : undefined}
      onRetry={home.reload}
    >
      <Stack gap="spacious">
        <div>
          <h1>创建 Project</h1>
          <p>选择 Owner 并创建一个新的 Project。</p>
        </div>
        {error && (
          <Banner variant="critical">
            <Banner.Title>{error.message}</Banner.Title>
            {(error.problems ?? []).length > 0 && (
              <Banner.Description>{(error.problems ?? []).join(' ')}</Banner.Description>
            )}
          </Banner>
        )}
        <Stack gap="normal">
          <FormControl required disabled={submitting}>
            <FormControl.Label>Owner</FormControl.Label>
            <Select
              block
              value={selectedOwner?.key ?? ''}
              onChange={(event) => setOwnerKey(event.target.value)}
            >
              <Select.Option value="" disabled>
                选择 Owner
              </Select.Option>
              {ownerOptions.map((option) => (
                <Select.Option key={option.key} value={option.key}>
                  {option.label}
                </Select.Option>
              ))}
            </Select>
            <FormControl.Caption>只能选择当前用户或你拥有的 User Group。</FormControl.Caption>
          </FormControl>
          <FormControl required disabled={submitting}>
            <FormControl.Label>Project 名称</FormControl.Label>
            <TextInput
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：图像分类实验"
              block
            />
          </FormControl>
          <FormControl disabled={submitting}>
            <FormControl.Label>说明（可选）</FormControl.Label>
            <Textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="说明这个 Project 用于什么任务"
              rows={5}
              block
              resize="vertical"
            />
          </FormControl>
        </Stack>
        <Stack direction="horizontal" gap="normal">
          <Button onClick={() => navigate(-1)} disabled={submitting}>
            取消
          </Button>
          <Button variant="primary" onClick={() => void submit()} loading={submitting}>
            创建 Project
          </Button>
        </Stack>
      </Stack>
    </AsyncState>
  )
}
