import { RunCommand } from '../runconfig/RunCommand'
import { Banner, Button, Dialog, Select, Spinner, TextInput } from '@primer/react'
import { useEffect, useRef, useState } from 'react'
import { ApiError, api, newIdempotencyKey } from '../../api/client'
import type { PreflightResult, Run, RunConfiguration } from '../../api/types'
import { describeComputeRequest } from '../../utils/format'
import { RunField } from '../runconfig/RunField'
import styles from '../runconfig/simpleRun.module.css'

interface Props {
  projectId: string
  configuration?: RunConfiguration | null
  versionId?: string
  versionLabel?: string
  defaultRunConfigurationId?: string | null
  onClose: () => void
  onSubmitted: (run: Run) => void
}

export function RunSubmissionDialog({
  projectId,
  configuration,
  versionId,
  versionLabel,
  defaultRunConfigurationId,
  onClose,
  onSubmitted,
}: Props) {
  const [configurations, setConfigurations] = useState<RunConfiguration[]>(
    configuration ? [configuration] : [],
  )
  const [selected, setSelected] = useState(configuration?.id ?? '')
  const [loading, setLoading] = useState(!configuration)
  const [loadError, setLoadError] = useState(false)
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [attempted, setAttempted] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [retry, setRetry] = useState(0)
  const [reload, setReload] = useState(0)
  const [name, setName] = useState('')
  const [showChoice, setShowChoice] = useState(false)
  const busy = useRef(false)
  const returnFocus = useRef(document.activeElement as HTMLElement | null)
  const intent = useRef({ key: newIdempotencyKey(), version: versionId })

  useEffect(() => {
    if (configuration) return
    let active = true
    setLoading(true)
    setLoadError(false)
    api
      .listRunConfigurations(projectId)
      .then((items) => {
        if (!active) return
        setConfigurations(items)
        setSelected(
          items.find((item) => item.id === defaultRunConfigurationId)?.id ??
            (items.length === 1 ? items[0]!.id : ''),
        )
      })
      .catch(() => {
        if (active) setLoadError(true)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [configuration, defaultRunConfigurationId, projectId, reload])

  useEffect(() => {
    if (!selected) {
      setChecking(false)
      return
    }
    let active = true
    setChecking(true)
    setPreflight(null)
    setError(null)
    api
      .preflight(projectId, {
        run_configuration_id: selected,
        project_version_id: intent.current.version,
      })
      .then((result) => {
        if (!active) return
        setPreflight(result)
        if (result.project_version_id) intent.current.version = result.project_version_id
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason : new Error())
      })
      .finally(() => {
        if (active) setChecking(false)
      })
    return () => {
      active = false
    }
  }, [projectId, selected, retry])

  const submit = async () => {
    if (
      busy.current ||
      checking ||
      !preflight?.ok ||
      !preflight.confirmation_token ||
      !preflight.project_version_id
    )
      return
    busy.current = true
    setAttempted(true)
    setSubmitting(true)
    setError(null)
    try {
      const run = await api.createRun(
        projectId,
        {
          run_configuration_id: selected,
          project_version_id: preflight.project_version_id,
          confirmation_token: preflight.confirmation_token,
          name,
        },
        intent.current.key,
      )
      onSubmitted(run)
      onClose()
    } catch (reason) {
      const failure = reason instanceof Error ? reason : new Error()
      setError(failure)
      // Definitive rejection requires a fresh preview; uncertain network failures retain the intent.
      if (
        failure instanceof ApiError &&
        [
          'run_confirmation_changed',
          'preflight_rejected',
          'permission_denied',
          'not_found',
        ].includes(failure.code)
      ) {
        setPreflight(null)
        setAttempted(false)
      }
    } finally {
      busy.current = false
      setSubmitting(false)
    }
  }
  const current = configurations.find((item) => item.id === selected)
  return (
    <Dialog
      title="提交 Run"
      returnFocusRef={returnFocus}
      width="medium"
      onClose={() => {
        if (!busy.current) onClose()
      }}
      footerButtons={[
        { content: '取消', disabled: submitting, onClick: onClose },
        {
          content: '提交 Run',
          buttonType: 'primary',
          disabled: checking || submitting || !preflight?.ok || !preflight.confirmation_token,
          loading: submitting,
          onClick: () => void submit(),
        },
      ]}
    >
      <div
        className={styles.form}
        onKeyDownCapture={(event) => {
          if (
            event.key === 'Escape' &&
            event.target instanceof Element &&
            event.target.closest('select')?.matches(':open')
          ) {
            event.stopPropagation()
          }
        }}
      >
        {loading ? (
          <p role="status">正在加载运行方案…</p>
        ) : loadError ? (
          <Banner variant="critical">
            <Banner.Title>运行方案加载失败</Banner.Title>
            <Banner.PrimaryAction onClick={() => setReload((v) => v + 1)}>
              重试
            </Banner.PrimaryAction>
          </Banner>
        ) : configurations.length === 0 ? (
          <p>还没有运行方案。请返回 Project 创建运行方案。</p>
        ) : (
          <>
            {showChoice || !selected ? (
              <RunField label="运行方案" disabled={submitting || attempted}>
                <Select
                  block
                  value={selected}
                  onChange={(e) => {
                    setPreflight(null)
                    setChecking(true)
                    setError(null)
                    setSelected(e.target.value)
                    intent.current = { key: newIdempotencyKey(), version: versionId }
                  }}
                >
                  <Select.Option value="">选择运行方案</Select.Option>
                  {configurations.map((c) => (
                    <Select.Option value={c.id} key={c.id}>
                      {c.name}
                    </Select.Option>
                  ))}
                </Select>
              </RunField>
            ) : (
              <div className={styles.header}>
                <span>
                  运行方案 <strong>{preflight?.configuration_name ?? current?.name}</strong>
                </span>
                {configurations.length > 1 && (
                  <Button
                    size="small"
                    variant="invisible"
                    disabled={submitting || attempted}
                    onClick={() => setShowChoice(true)}
                  >
                    更换
                  </Button>
                )}
              </div>
            )}
          </>
        )}
        {checking && (
          <div className={styles.row} role="status">
            <Spinner size="small" />
            正在检查运行配置…
          </div>
        )}
        {error && (
          <Banner variant="critical">
            <Banner.Title>
              {error instanceof ApiError && error.code === 'run_confirmation_changed'
                ? '运行配置已变化'
                : '无法提交 Run'}
            </Banner.Title>
            <Banner.Description>
              {preflight
                ? '请检查网络连接后重试。同一次提交不会重复创建 Run。'
                : '请刷新摘要，确认配置与当前使用权限后重试。'}
              {error instanceof ApiError && error.requestId && (
                <p className={styles.muted}>请求标识：{error.requestId}</p>
              )}
            </Banner.Description>
          </Banner>
        )}
        {preflight && !preflight.ok && (
          <Banner variant="warning">
            <Banner.Title>暂时无法提交 Run</Banner.Title>
            <Banner.Description>
              <ul>
                {preflight.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
              请修正配置或使用权限后重新检查。
            </Banner.Description>
          </Banner>
        )}
        {!checking && selected && (!preflight || !preflight.ok) && !loading && (
          <div>
            <Button
              disabled={submitting}
              onClick={() => {
                intent.current.key = newIdempotencyKey()
                setRetry((v) => v + 1)
              }}
            >
              刷新摘要
            </Button>
          </div>
        )}
        {preflight && (
          <>
            <dl className={styles.summary}>
              <dt>Project 版本</dt>
              <dd>{preflight.project_version_label ?? versionLabel ?? '尚未创建版本'}</dd>
              <dt>运行环境</dt>
              <dd>
                {preflight.environment_version
                  ? `${preflight.environment_name ?? '运行环境'} · ${preflight.environment_version.version}`
                  : '当前不可用'}
              </dd>
              <dt>算力方案</dt>
              <dd>
                {preflight.compute_plan_name ?? '当前不可用'}
                {preflight.compute_request && (
                  <p className={styles.muted}>
                    {describeComputeRequest(preflight.compute_request)}
                  </p>
                )}
              </dd>
            </dl>
            <RunCommand command={preflight.command} />
            <details className={styles.disclosure}>
              <summary>配置详情</summary>
              <div className={styles.section}>
                <dl className={styles.summary}>
                  <dt>运行输入</dt>
                  <dd>
                    {preflight.input_bindings.length
                      ? preflight.input_bindings.map((b) => (
                          <div key={`${b.source_id}:${b.access_path}`}>
                            <code>
                              {b.source_id}
                              {b.source_subpath ? `/${b.source_subpath}` : ''}
                            </code>{' '}
                            → <code>{b.access_path}</code>
                          </div>
                        ))
                      : '无'}
                  </dd>
                  <dt>运行产物</dt>
                  <dd>
                    {preflight.artifact_rules.length
                      ? preflight.artifact_rules.map((r) => (
                          <div key={r.path}>
                            <code>{r.path}</code>
                            {r.optional ? '（可选）' : '（必须生成）'}
                          </div>
                        ))
                      : '不收集'}
                  </dd>
                  <dt>工作目录</dt>
                  <dd>
                    <code>{preflight.working_directory}</code>
                  </dd>
                  <dt>参数</dt>
                  <dd>
                    {Object.entries(preflight.resolved_environment_variables).map(
                      ([key, value]) => (
                        <div key={key}>
                          <code>
                            {key}={value}
                          </code>
                        </div>
                      ),
                    )}
                    {Object.entries(preflight.secret_references).map(([key]) => (
                      <div key={key}>
                        <code>{key}</code>（Secret 引用）
                      </div>
                    ))}
                    {!Object.keys(preflight.resolved_environment_variables).length &&
                    !Object.keys(preflight.secret_references).length
                      ? '无'
                      : null}
                  </dd>
                </dl>
                <p className={styles.muted}>程序输出自动记录为日志；运行产物按规则单独保存。</p>
                <RunField
                  label="Run 名称"
                  caption="留空自动生成"
                  disabled={submitting || attempted}
                >
                  <TextInput block value={name} onChange={(e) => setName(e.target.value)} />
                </RunField>
              </div>
            </details>
          </>
        )}
      </div>
    </Dialog>
  )
}
