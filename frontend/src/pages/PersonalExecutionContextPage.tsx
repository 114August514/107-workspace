import { Banner, Button, FormControl, Label, TextInput } from '@primer/react'
import { Card } from '@primer/react/experimental'
import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import type { Home, Variable } from '../api/types'
import { useAsync, type AsyncState as AsyncResource } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { formatTime } from '../utils/format'
import styles from './PersonalExecutionContextPage.module.css'

interface Props {
  username: string
  home: AsyncResource<Home>
}

export function PersonalExecutionContextPage({ username, home }: Props) {
  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>个人执行上下文</h1>
        <p className={styles.subtitle}>管理发起 Run 时属于你本人的算力权益与配置。</p>
      </header>
      <AsyncState
        loading={home.loading}
        loadingText="正在加载个人执行上下文…"
        error={toAsyncError(home.error)}
        onRetry={home.reload}
      >
        {home.data ? <ExecutionContext username={username} home={home.data} /> : null}
      </AsyncState>
    </div>
  )
}

function ExecutionContext({ username, home }: { username: string; home: Home }) {
  const user = home.user
  const variables = useAsync<Variable[]>(() => api.listUserVariables(user.id), [username, user.id])
  const secrets = useAsync<string[]>(() => api.listUserSecrets(user.id), [username, user.id])

  return (
    <div className={styles.content}>
      <section className={styles.identity} aria-labelledby="personal-identity-title">
        <div>
          <h2 id="personal-identity-title" className={styles.sectionTitle}>
            当前用户
          </h2>
          <p className={styles.identityName}>{user.display_name}</p>
          <p className={styles.muted}>@{user.username}</p>
        </div>
        <p className={styles.identityNote}>
          这里的配置只属于 Initiated By User，不随 User Group Membership 转移。
        </p>
      </section>

      <Card
        as="section"
        padding="normal"
        className={styles.card}
        aria-label="Resource Entitlements"
      >
        <h2 className={styles.sectionTitle}>Resource Entitlements</h2>
        {home.personal_execution_context.entitlements.length === 0 ? (
          <div className={styles.empty}>
            <strong>当前没有 Resource Entitlement</strong>
            <span>因此无法选择 Compute Plan 提交 Run；权益由平台发放。</span>
          </div>
        ) : (
          <ul className={styles.entitlementList}>
            {home.personal_execution_context.entitlements.map((entitlement) => (
              <li key={entitlement.id} className={styles.entitlement}>
                <div className={styles.rowHeading}>
                  <strong>{entitlement.compute_plan_name}</strong>
                  <Label variant={entitlement.status === 'expired' ? 'danger' : 'success'}>
                    {entitlement.status === 'expired' ? '已过期' : '有效'}
                  </Label>
                </div>
                <span className={styles.muted}>Compute Plan：{entitlement.compute_plan_id}</span>
                <span className={styles.muted}>
                  有效期：{entitlement.expires_at ? formatTime(entitlement.expires_at) : '长期有效'}
                </span>
                {entitlement.status_reason ? (
                  <span className={styles.expiredReason}>{entitlement.status_reason}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className={styles.configGrid}>
        <VariableSection userId={user.id} state={variables} />
        <SecretSection userId={user.id} state={secrets} />
      </div>

      <Card as="section" padding="normal" className={styles.card} aria-label="配置引用说明">
        <h2 className={styles.sectionTitle}>在 Run Configuration 中引用</h2>
        <div className={styles.referenceGrid}>
          <div>
            <h3 className={styles.referenceTitle}>当前 User</h3>
            <code>{'${{ user.vars.NAME }}'}</code>
            <code>{'${{ user.secrets.NAME }}'}</code>
            <p>只读取 Initiated By User 的个人配置，不回退到 Project。</p>
          </div>
          <div>
            <h3 className={styles.referenceTitle}>Project / Project Owner</h3>
            <code>{'${{ vars.NAME }}'}</code>
            <code>{'${{ secrets.NAME }}'}</code>
            <p>先读取 Project，再回退到该 Project 的直接 Owner。</p>
          </div>
        </div>
        <Banner>
          <Banner.Title>Run Snapshot 保持不变</Banner.Title>
          <Banner.Description>
            创建 Run 时会固定解析结果；修改个人配置不会回写已有 Run Snapshot。
          </Banner.Description>
        </Banner>
      </Card>
    </div>
  )
}

function VariableSection({ userId, state }: { userId: string; state: AsyncResource<Variable[]> }) {
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{ error: boolean; message: string } | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedName = name.trim()
    if (!normalizedName) return
    setSubmitting(true)
    setFeedback(null)
    try {
      await api.setUserVariable(userId, { name: normalizedName, value })
      setName('')
      setValue('')
      setEditing(null)
      setFeedback({ error: false, message: 'Variable 已保存。' })
      await state.reload({ silent: true })
    } catch {
      setFeedback({ error: true, message: 'Variable 保存失败，请重试。' })
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (variableName: string) => {
    setFeedback(null)
    try {
      await api.deleteUserVariable(userId, variableName)
      if (editing === variableName) {
        setEditing(null)
        setName('')
        setValue('')
      }
      await state.reload({ silent: true })
    } catch {
      setFeedback({ error: true, message: 'Variable 删除失败，请重试。' })
    }
  }

  return (
    <Card as="section" padding="normal" className={styles.card} aria-label="User Variables">
      <h2 className={styles.sectionTitle}>User Variables</h2>
      <form className={styles.form} onSubmit={submit}>
        <FormControl id="user-variable-name" required disabled={submitting}>
          <FormControl.Label>Variable 名称</FormControl.Label>
          <TextInput
            aria-label="Variable 名称"
            block
            value={name}
            readOnly={editing !== null}
            placeholder="例如 THREADS"
            onChange={(event) => setName(event.target.value)}
          />
        </FormControl>
        <FormControl id="user-variable-value" disabled={submitting}>
          <FormControl.Label>Variable 值</FormControl.Label>
          <TextInput
            aria-label="Variable 值"
            block
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </FormControl>
        <div className={styles.formActions}>
          <Button type="submit" variant="primary" loading={submitting} disabled={!name.trim()}>
            {editing ? '保存 Variable' : '创建 Variable'}
          </Button>
          {editing ? (
            <Button
              type="button"
              onClick={() => {
                setEditing(null)
                setName('')
                setValue('')
              }}
            >
              取消编辑
            </Button>
          ) : null}
        </div>
      </form>
      <MutationFeedback feedback={feedback} />
      <AsyncState
        loading={state.loading}
        loadingText="正在加载 User Variables…"
        error={toAsyncError(state.error)}
        onRetry={state.reload}
        empty={(state.data?.length ?? 0) === 0}
        emptyText="还没有 User Variable"
      >
        <ul className={styles.configList}>
          {(state.data ?? []).map((variable) => (
            <li key={variable.name} className={styles.configItem}>
              <div className={styles.configValue}>
                <strong>{variable.name}</strong>
                <span>{variable.value}</span>
              </div>
              <div className={styles.rowActions}>
                <Button
                  size="small"
                  aria-label={`编辑 ${variable.name}`}
                  onClick={() => {
                    setEditing(variable.name)
                    setName(variable.name)
                    setValue(variable.value)
                  }}
                >
                  编辑
                </Button>
                <Button
                  size="small"
                  variant="danger"
                  aria-label={`删除 ${variable.name} Variable`}
                  onClick={() => void remove(variable.name)}
                >
                  删除
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </AsyncState>
    </Card>
  )
}

function SecretSection({ userId, state }: { userId: string; state: AsyncResource<string[]> }) {
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [replacing, setReplacing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{ error: boolean; message: string } | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedName = name.trim()
    if (!normalizedName || !value) return
    setSubmitting(true)
    setFeedback(null)
    try {
      await api.setUserSecret(userId, { name: normalizedName, value })
      setValue('')
      setName('')
      setReplacing(false)
      setFeedback({ error: false, message: 'Secret 已安全保存；值不会回显。' })
      await state.reload({ silent: true })
    } catch {
      setFeedback({ error: true, message: 'Secret 保存失败，请重试。' })
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (secretName: string) => {
    setFeedback(null)
    try {
      await api.deleteUserSecret(userId, secretName)
      if (name === secretName) {
        setName('')
        setValue('')
        setReplacing(false)
      }
      await state.reload({ silent: true })
    } catch {
      setFeedback({ error: true, message: 'Secret 删除失败，请重试。' })
    }
  }

  return (
    <Card as="section" padding="normal" className={styles.card} aria-label="User Secrets">
      <h2 className={styles.sectionTitle}>User Secrets</h2>
      <p className={styles.muted}>只显示名称。Secret 值提交后不会回显。</p>
      <form className={styles.form} onSubmit={submit}>
        <FormControl id="user-secret-name" required disabled={submitting}>
          <FormControl.Label>Secret 名称</FormControl.Label>
          <TextInput
            aria-label="Secret 名称"
            block
            value={name}
            readOnly={replacing}
            placeholder="例如 API_TOKEN"
            onChange={(event) => setName(event.target.value)}
          />
        </FormControl>
        <FormControl id="user-secret-value" required disabled={submitting}>
          <FormControl.Label>Secret 值</FormControl.Label>
          <TextInput
            aria-label="Secret 值"
            block
            type="password"
            autoComplete="new-password"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </FormControl>
        <div className={styles.formActions}>
          <Button
            type="submit"
            variant="primary"
            loading={submitting}
            disabled={!name.trim() || !value}
          >
            {replacing ? '替换 / 轮换 Secret' : '创建 Secret'}
          </Button>
          {replacing ? (
            <Button
              type="button"
              onClick={() => {
                setReplacing(false)
                setName('')
                setValue('')
              }}
            >
              取消替换
            </Button>
          ) : null}
        </div>
      </form>
      <MutationFeedback feedback={feedback} />
      <AsyncState
        loading={state.loading}
        loadingText="正在加载 User Secrets…"
        error={toAsyncError(state.error)}
        onRetry={state.reload}
        empty={(state.data?.length ?? 0) === 0}
        emptyText="还没有 User Secret"
      >
        <ul className={styles.configList}>
          {(state.data ?? []).map((secretName) => (
            <li key={secretName} className={styles.configItem}>
              <strong>{secretName}</strong>
              <div className={styles.rowActions}>
                <Button
                  size="small"
                  aria-label={`替换或轮换 ${secretName}`}
                  onClick={() => {
                    setReplacing(true)
                    setName(secretName)
                    setValue('')
                  }}
                >
                  替换 / 轮换
                </Button>
                <Button
                  size="small"
                  variant="danger"
                  aria-label={`删除 ${secretName} Secret`}
                  onClick={() => void remove(secretName)}
                >
                  删除
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </AsyncState>
    </Card>
  )
}

function MutationFeedback({ feedback }: { feedback: { error: boolean; message: string } | null }) {
  if (!feedback) return null
  return (
    <Banner variant={feedback.error ? 'critical' : 'success'}>
      <Banner.Title>{feedback.message}</Banner.Title>
    </Banner>
  )
}
