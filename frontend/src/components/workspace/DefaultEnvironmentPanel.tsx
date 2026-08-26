import { Button, Flash, FormControl, Label, Link, Text } from '@primer/react'
import { useEffect, useMemo, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { api } from '../../api/client'
import type { Environment, EnvironmentVersion, UserGroup } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { normalizeError } from '../common/asyncStateError'
import styles from './DefaultEnvironmentPanel.module.css'

interface Props {
  userGroup: UserGroup
  onUserGroupChanged: () => void
}

export function DefaultEnvironmentPanel({ userGroup, onUserGroupChanged }: Props) {
  const environments = useAsync<Environment[]>(
    () => api.environmentsForUserGroup(userGroup.id),
    [userGroup.id],
  )
  const [selectedVersionId, setSelectedVersionId] = useState(
    userGroup.default_environment_version_id ?? '',
  )
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{
    variant: 'success' | 'danger'
    text: string
  } | null>(null)

  useEffect(() => {
    setSelectedVersionId(userGroup.default_environment_version_id ?? '')
  }, [userGroup.id, userGroup.default_environment_version_id])

  useEffect(() => {
    setFeedback(null)
  }, [userGroup.id])

  const versions = useMemo(
    () =>
      (environments.data ?? []).flatMap((environment) =>
        environment.versions.map((version) => ({ environment, version })),
      ),
    [environments.data],
  )
  const current = versions.find(
    ({ version }) => version.id === userGroup.default_environment_version_id,
  )
  const selected = versions.find(({ version }) => version.id === selectedVersionId)
  const canUpdate = userGroup.capabilities?.includes('user_group.update') ?? false
  const unchanged = selectedVersionId === (userGroup.default_environment_version_id ?? '')
  const invalidSelection = Boolean(selectedVersionId) && (!selected || !selected.version.available)

  const save = async () => {
    setSubmitting(true)
    setFeedback(null)
    try {
      await api.updateUserGroup(userGroup.id, {
        default_environment_version_id: selectedVersionId || null,
      })
      setFeedback({ variant: 'success', text: '已更新默认 Environment Version。' })
      onUserGroupChanged()
    } catch (error) {
      setFeedback({ variant: 'danger', text: (error as Error).message })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className={styles.panel} aria-labelledby="default-environment-title">
      <header className={styles.header}>
        <div>
          <h2 id="default-environment-title" className={styles.title}>
            默认 Environment Version
          </h2>
          <Text as="p" className={styles.description}>
            供新运行方案选择时参考；已经保存的 Run Configuration 不会随默认值漂移。
          </Text>
        </div>
        <Label variant={current?.version.available ? 'success' : 'default'}>
          {userGroup.default_environment_version_id ? '已设置' : '未设置'}
        </Label>
      </header>

      <div className={styles.current}>
        <Text weight="semibold">当前默认：</Text>
        {current ? (
          <Link as={RouterLink} to={`/environment-versions/${current.version.id}`}>
            {current.environment.name} · {current.version.version}
          </Link>
        ) : userGroup.default_environment_version_id ? (
          <>
            <span>{userGroup.default_environment_version_id}</span>
            <Label variant="attention">当前不可使用</Label>
          </>
        ) : (
          <Text className={styles.currentDescription}>无</Text>
        )}
      </div>

      {feedback ? <Flash variant={feedback.variant}>{feedback.text}</Flash> : null}

      <AsyncState
        loading={environments.loading}
        loadingText="正在加载可用运行环境…"
        error={normalizeError(environments.error)}
        onRetry={environments.reload}
        empty={!environments.loading && environments.data?.length === 0}
        emptyText="当前没有可供这个 User Group 使用的运行环境。"
        emptyDescription="默认值保持不变；资产 Owner 建立 USE Grant 后可在这里选择。"
      >
        {environments.data && environments.data.length > 0 ? (
          <div className={styles.form}>
            <FormControl disabled={!canUpdate || submitting} id="default-environment-version">
              <FormControl.Label>选择确定版本</FormControl.Label>
              <select
                className={styles.select}
                value={selectedVersionId}
                onChange={(event) => {
                  setSelectedVersionId(event.target.value)
                  setFeedback(null)
                }}
                id="default-environment-version"
                aria-describedby="default-environment-version-caption"
                disabled={!canUpdate || submitting}
              >
                <option value="">不设置默认版本</option>
                {environments.data.map((environment) => (
                  <optgroup
                    key={environment.id}
                    label={`${environment.name} · ${environment.owner.display_name}`}
                  >
                    {environment.versions.map((version: EnvironmentVersion) => (
                      <option key={version.id} value={version.id} disabled={!version.available}>
                        {version.version}
                        {version.available ? '' : '（当前不可用）'}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <FormControl.Caption>
                这里只改变默认选择，不修改任何已保存运行方案的精确引用。
              </FormControl.Caption>
              {invalidSelection ? (
                <FormControl.Validation variant="error">
                  这个版本当前不可用或已失去 USE 资格，请选择其他可用版本。
                </FormControl.Validation>
              ) : null}
            </FormControl>
            {canUpdate ? (
              <Button
                variant="primary"
                disabled={submitting || unchanged || invalidSelection}
                onClick={() => void save()}
              >
                {submitting ? '保存中…' : '保存默认版本'}
              </Button>
            ) : null}
          </div>
        ) : null}
      </AsyncState>
    </section>
  )
}
