import { Banner, Button, FormControl, Select, Textarea, TextInput } from '@primer/react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Home, OwnerReference } from '../api/types'
import { useAsync, type AsyncState as AsyncResource } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import styles from './CreateAssetPage.module.css'

export function CreateAssetPage({
  kind,
  home,
}: {
  kind: 'environment' | 'shared-resource'
  home: AsyncResource<Home>
}) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const groups = useAsync(() => api.listUserGroups(), [])
  const [ownerKey, setOwnerKey] = useState(params.get('owner') ?? '')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const title = kind === 'environment' ? '创建运行环境' : '创建共享资源'
  const user = home.data?.user
  const owners: { key: string; name: string; owner: OwnerReference }[] = [
    ...(user
      ? [
          {
            key: `user:${user.id}`,
            name: `${user.display_name}（个人）`,
            owner: { kind: 'user' as const, id: user.id },
          },
        ]
      : []),
    ...(groups.data ?? []).map((group) => ({
      key: `user_group:${group.id}`,
      name: group.name,
      owner: { kind: 'user_group' as const, id: group.id },
    })),
  ]
  // A stale or unauthorized explicit owner must never silently become the personal owner.
  const selected = ownerKey ? owners.find((owner) => owner.key === ownerKey) : owners[0]
  const submit = async () => {
    if (busy) return
    if (!selected || !name.trim()) {
      setError('请填写名称并选择可用的所属范围。')
      return
    }
    setBusy(true)
    setError('')
    try {
      const payload = { owner: selected.owner, name: name.trim(), description: description.trim() }
      const result =
        kind === 'environment'
          ? await api.createEnvironment(payload)
          : await api.createSharedResource(payload)
      navigate(`/${kind === 'environment' ? 'environments' : 'shared-resources'}/${result.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '创建失败，请重试。')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{title}</h1>
      <p className={styles.description}>填写基本信息，创建后可在详情页发布版本。</p>
      <AsyncState
        loading={home.loading || groups.loading}
        loadingText="正在加载所属范围…"
        error={home.error || groups.error ? { message: '无法加载所属范围。' } : undefined}
        onRetry={() => {
          void home.reload()
          void groups.reload()
        }}
      >
        {error && (
          <Banner variant="critical">
            <Banner.Title>{error}</Banner.Title>
          </Banner>
        )}
        <form
          className={styles.form}
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
        >
          <FormControl required disabled={busy}>
            <FormControl.Label>所属范围</FormControl.Label>
            {owners.length === 1 && selected ? (
              <p>{selected.name}</p>
            ) : (
              <Select
                block
                value={selected?.key ?? ''}
                onChange={(event) => setOwnerKey(event.target.value)}
              >
                <Select.Option value="" disabled>
                  请选择所属范围
                </Select.Option>
                {owners.map((owner) => (
                  <Select.Option key={owner.key} value={owner.key}>
                    {owner.name}
                  </Select.Option>
                ))}
              </Select>
            )}
            {ownerKey && !selected && (
              <FormControl.Validation variant="error">
                该所属范围已不可用，请重新选择。
              </FormControl.Validation>
            )}
          </FormControl>
          <FormControl required disabled={busy}>
            <FormControl.Label>名称</FormControl.Label>
            <TextInput
              block
              value={name}
              maxLength={128}
              onChange={(event) => setName(event.target.value)}
            />
          </FormControl>
          <FormControl disabled={busy}>
            <FormControl.Label>说明</FormControl.Label>
            <Textarea
              block
              rows={4}
              resize="vertical"
              value={description}
              maxLength={4096}
              onChange={(event) => setDescription(event.target.value)}
            />
          </FormControl>
          <div className={styles.actions}>
            <Button onClick={() => navigate(-1)} disabled={busy}>
              取消
            </Button>
            <Button type="submit" variant="primary" loading={busy} disabled={busy || !selected}>
              {title}
            </Button>
          </div>
        </form>
      </AsyncState>
    </div>
  )
}
