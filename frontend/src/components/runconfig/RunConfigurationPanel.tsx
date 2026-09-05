import { KebabHorizontalIcon, PlayIcon, PlusIcon } from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Banner,
  Button,
  ConfirmationDialog,
  IconButton,
  Label,
} from '@primer/react'
import { useState } from 'react'
import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { can } from '../../api/types'
import type { Project, RunConfiguration } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { RunCommand } from './RunCommand'
import { RunConfigurationModal } from './RunConfigurationModal'
import styles from './simpleRun.module.css'

interface Props {
  projectId: string
  access: Project | undefined
  defaultConfigurationId: string | null
  onSubmitRun: (configuration: RunConfiguration) => void
  onChanged: () => void
}
export function RunConfigurationPanel({
  projectId,
  access,
  defaultConfigurationId,
  onSubmitRun,
  onChanged,
}: Props) {
  const canManage = can(access, 'run_configuration.manage')
  const canSubmit = can(access, 'run.submit')
  const canDefault = can(access, 'project.update')
  const configurations = useAsync(() => api.listRunConfigurations(projectId), [projectId])
  const choices = useAsync(async () => {
    const [plans, environments, entitlements] = await Promise.all([
      api.computePlans(),
      api.environmentsForProject(projectId),
      api.listEntitlements(),
    ])
    return {
      plans,
      environments,
      usablePlans: plans.filter((p) =>
        entitlements.some((e) => e.compute_plan_id === p.id && e.status === 'active'),
      ),
    }
  }, [projectId])
  const [editing, setEditing] = useState<RunConfiguration | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<RunConfiguration | null>(null)
  const [pending, setPending] = useState(false)
  const [feedback, setFeedback] = useState<{ error: boolean; text: string } | null>(null)
  const changed = () => {
    void configurations.reload()
    onChanged()
  }
  const setDefault = async (id: string | null) => {
    setPending(true)
    setFeedback(null)
    try {
      await api.updateProject(projectId, { default_run_configuration_id: id })
      onChanged()
      setFeedback({ error: false, text: id ? '默认运行方案已更新' : '已取消默认运行方案' })
    } catch {
      setFeedback({ error: true, text: '默认运行方案保存失败，请重试。' })
    } finally {
      setPending(false)
    }
  }
  const remove = async (configuration: RunConfiguration) => {
    setPending(true)
    setFeedback(null)
    try {
      await api.deleteRunConfiguration(configuration.id)
      changed()
      setFeedback({ error: false, text: '运行方案已删除' })
    } catch {
      setFeedback({ error: true, text: '运行方案删除失败，请重试。' })
    } finally {
      setPending(false)
    }
  }
  return (
    <section className={styles.panel} aria-label="运行方案">
      <div className={styles.header}>
        <h2 className={styles.title}>运行方案</h2>
        {canManage && (
          <Button
            variant="primary"
            leadingVisual={PlusIcon}
            disabled={!choices.data || choices.loading || !!choices.error}
            onClick={() => {
              setFeedback(null)
              setEditing(null)
            }}
          >
            新建运行方案
          </Button>
        )}
      </div>
      <p className={styles.muted}>保存程序的运行方式，下次选择方案即可提交 Run。</p>
      {feedback && (
        <Banner variant={feedback.error ? 'critical' : 'success'}>
          <Banner.Title>{feedback.text}</Banner.Title>
        </Banner>
      )}
      <AsyncState
        loading={choices.loading}
        loadingText="正在加载运行环境与算力方案…"
        error={toAsyncError(choices.error)}
        onRetry={choices.reload}
      >
        {null}
      </AsyncState>
      <AsyncState
        loading={configurations.loading}
        loadingText="正在加载运行方案…"
        error={toAsyncError(configurations.error)}
        onRetry={configurations.reload}
        empty={!configurations.data?.length}
        emptyText="还没有运行方案"
        emptyDescription={
          canManage ? '创建运行方案，保存执行命令、运行环境与算力需求。' : undefined
        }
      >
        <ul className={styles.list}>
          {configurations.data?.map((configuration) => {
            const environment = choices.data?.environments.find((e) =>
              e.versions.some((v) => v.id === configuration.environment_version_id),
            )
            const version = environment?.versions.find(
              (v) => v.id === configuration.environment_version_id,
            )
            const plan = choices.data?.plans.find((p) => p.id === configuration.compute_plan_id)
            return (
              <li key={configuration.id} className={styles.section}>
                <div className={styles.header}>
                  <div className={styles.row}>
                    <strong className={styles.configurationName}>{configuration.name}</strong>
                    {configuration.id === defaultConfigurationId && (
                      <Label variant="accent">默认</Label>
                    )}
                  </div>
                  <div className={styles.actions}>
                    {canSubmit && (
                      <Button leadingVisual={PlayIcon} onClick={() => onSubmitRun(configuration)}>
                        提交 Run
                      </Button>
                    )}
                    {(canManage || canDefault) && (
                      <ActionMenu>
                        <ActionMenu.Anchor>
                          <IconButton
                            icon={KebabHorizontalIcon}
                            variant="invisible"
                            aria-label={`${configuration.name} 的更多操作`}
                            disabled={pending}
                          />
                        </ActionMenu.Anchor>
                        <ActionMenu.Overlay align="end" width="auto">
                          <ActionList>
                            {canManage && (
                              <ActionList.Item
                                disabled={!choices.data || pending}
                                onSelect={() => setEditing(configuration)}
                              >
                                编辑
                              </ActionList.Item>
                            )}
                            {canDefault && (
                              <ActionList.Item
                                disabled={pending}
                                onSelect={() =>
                                  void setDefault(
                                    configuration.id === defaultConfigurationId
                                      ? null
                                      : configuration.id,
                                  )
                                }
                              >
                                {configuration.id === defaultConfigurationId
                                  ? '取消默认'
                                  : '设为默认'}
                              </ActionList.Item>
                            )}
                            {canManage && (
                              <>
                                <ActionList.Divider />
                                <ActionList.Item
                                  variant="danger"
                                  disabled={pending}
                                  onSelect={() => setDeleting(configuration)}
                                >
                                  删除
                                </ActionList.Item>
                              </>
                            )}
                          </ActionList>
                        </ActionMenu.Overlay>
                      </ActionMenu>
                    )}
                  </div>
                </div>
                <p className={styles.muted}>
                  {environment
                    ? `${environment.name} · ${version?.version}${version?.availability !== 'available' ? '（当前不可用）' : ''}`
                    : '运行环境待确认'}{' '}
                  · {plan?.name ?? '算力方案待确认'}
                </p>
                <RunCommand command={configuration.command} />
              </li>
            )
          })}
        </ul>
      </AsyncState>
      {editing !== undefined && choices.data && (
        <RunConfigurationModal
          open
          projectId={projectId}
          defaultEnvironmentVersionId={access?.environment_version_id}
          editing={editing}
          plans={choices.data.plans}
          preferredPlanId={
            choices.data.usablePlans.length === 1 ? choices.data.usablePlans[0]!.id : undefined
          }
          environments={choices.data.environments}
          onClose={() => setEditing(undefined)}
          onSaved={() => {
            changed()
            setFeedback({ error: false, text: editing ? '运行方案已更新' : '运行方案已创建' })
          }}
        />
      )}
      {deleting && (
        <ConfirmationDialog
          title={`删除运行方案“${deleting.name}”？`}
          confirmButtonContent="删除运行方案"
          confirmButtonType="danger"
          cancelButtonContent="取消"
          onClose={(gesture) => {
            const target = deleting
            setDeleting(null)
            if (gesture === 'confirm') void remove(target)
          }}
        >
          已经创建的 Run 不受影响，它们按各自的运行快照执行。
        </ConfirmationDialog>
      )}
    </section>
  )
}
