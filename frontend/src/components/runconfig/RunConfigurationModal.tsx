import { Banner, Button, Checkbox, Dialog, Select, Textarea, TextInput } from '@primer/react'
import { useRef, useState } from 'react'
import { ApiError, api } from '../../api/client'
import type {
  ComputePlan,
  Environment,
  RunConfiguration,
  RunConfigurationInput,
} from '../../api/types'
import { describeComputeRequest } from '../../utils/format'
import { RunField } from './RunField'
import { SharedResourceInputBindings } from './SharedResourceInputBindings'
import styles from './simpleRun.module.css'

interface Props {
  open: boolean
  projectId: string
  plans: ComputePlan[]
  environments: Environment[]
  preferredPlanId?: string
  defaultEnvironmentVersionId?: string | null
  editing?: RunConfiguration | null
  onClose: () => void
  onSaved: () => void
}

function defaults(plan?: ComputePlan) {
  return {
    nodes: plan?.default_nodes ?? 1,
    cpus: plan?.default_cpus ?? 1,
    memory_mb: plan?.default_memory_mb ?? 1024,
    gpus: plan?.default_gpus ?? 0,
    time_limit_minutes: plan?.default_time_limit_minutes ?? 30,
  }
}

export function RunConfigurationModal(props: Props) {
  return props.open ? <ConfigurationEditor {...props} key={props.editing?.id ?? 'new'} /> : null
}

function ConfigurationEditor({
  projectId,
  plans,
  environments,
  editing,
  preferredPlanId,
  defaultEnvironmentVersionId,
  onClose,
  onSaved,
}: Props) {
  const versions = environments.flatMap((environment) =>
    environment.versions.map((version) => ({ environment, version })),
  )
  const available = versions.filter(({ version }) => version.availability === 'available')
  const [data, setData] = useState<RunConfigurationInput>(() => ({
    name: editing?.name ?? '默认运行',
    description: editing?.description ?? '',
    command: editing?.command ?? '',
    working_directory: editing?.working_directory ?? '.',
    compute_plan_id:
      editing?.compute_plan_id ?? preferredPlanId ?? (plans.length === 1 ? plans[0]!.id : ''),
    environment_version_id:
      editing?.environment_version_id ??
      (available.some(({ version }) => version.id === defaultEnvironmentVersionId)
        ? defaultEnvironmentVersionId!
        : available.length === 1
          ? available[0]!.version.id
          : ''),
    compute_request: editing?.compute_request ?? null,
    environment_variables: editing?.environment_variables ?? {},
    input_bindings: editing?.input_bindings ?? [],
    artifact_rules: editing?.artifact_rules ?? [{ path: 'outputs/', name: '', optional: true }],
  }))
  const [parameters, setParameters] = useState(() =>
    Object.entries(editing?.environment_variables ?? {}).map(([name, value]) => ({ name, value })),
  )
  const [custom, setCustom] = useState(!!editing?.compute_request)
  const [resourcesOpen, setResourcesOpen] = useState(false)
  const plan = plans.find((p) => p.id === data.compute_plan_id)
  const [request, setRequest] = useState(() => editing?.compute_request ?? defaults(plan))
  const [advanced, setAdvanced] = useState(false)
  const [outputs, setOutputs] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<Error | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const busy = useRef(false)
  const form = useRef<HTMLFormElement>(null)
  const commandInput = useRef<HTMLTextAreaElement>(null)
  const returnFocus = useRef(document.activeElement as HTMLElement | null)
  const patch = (change: Partial<RunConfigurationInput>) =>
    setData((old) => ({ ...old, ...change }))
  const bindings = data.input_bindings ?? []
  const rules = data.artifact_rules ?? []
  const selectedVersion = versions.find(({ version }) => version.id === data.environment_version_id)

  const submit = async () => {
    if (busy.current) return
    const problems: Record<string, string> = {}
    if (!data.command.trim()) problems.command = '请填写执行命令'
    if (!data.environment_version_id) problems.environment = '请选择运行环境'
    if (!data.compute_plan_id) problems.compute = '请选择算力方案'
    if (!data.name.trim()) problems.name = '请填写方案名称'
    const work = data.working_directory ?? '.'
    if (work.startsWith('/') || work.replaceAll('\\', '/').split('/').includes('..'))
      problems.work = '工作目录必须在 Project 根目录内'
    if (
      parameters.some((p) => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(p.name)) ||
      new Set(parameters.map((p) => p.name)).size !== parameters.length
    )
      problems.parameters = '参数名称需使用字母、数字或下划线，不能以数字开头或重复'
    if (
      bindings.some(
        (b) =>
          !b.source_id ||
          !b.access_path.startsWith('/') ||
          b.access_path.replaceAll('\\', '/').split('/').includes('..'),
      )
    )
      problems.inputs = '请选择确定资源版本，并填写以 / 开头且不包含 .. 的输入访问路径'
    const paths = bindings.map(
      (b) =>
        '/' +
        b.access_path
          .split('/')
          .filter((p) => p && p !== '.')
          .join('/'),
    )
    if (
      paths.some((path, i) =>
        paths.some(
          (other, j) => i !== j && (path === other || path === '/' || other.startsWith(path + '/')),
        ),
      )
    )
      problems.inputs = '输入访问路径不能重复或互相包含'
    if (rules.some((r) => !r.path.trim())) problems.outputs = '请填写产物路径，或删除空规则'
    if (custom && plan) {
      for (const [key] of resourceFields) {
        if (
          !Number.isInteger(request[key]) ||
          request[key]! < (key === 'gpus' ? 0 : 1) ||
          request[key]! > plan[`max_${key}`]
        ) {
          problems[`resource_${key}`] =
            `请输入 ${key === 'gpus' ? 0 : 1} 至 ${plan[`max_${key}`]} 之间的整数`
        }
      }
    }
    setErrors(problems)
    if (Object.keys(problems).length) {
      if (problems.work || problems.parameters || problems.inputs) setAdvanced(true)
      if (problems.outputs) setOutputs(true)
      if (Object.keys(problems).some((key) => key.startsWith('resource_'))) setResourcesOpen(true)
      requestAnimationFrame(() =>
        form.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(),
      )
      return
    }
    busy.current = true
    setSubmitting(true)
    setError(null)
    try {
      const payload = {
        ...data,
        working_directory: work || '.',
        compute_request: custom ? request : null,
        environment_variables: Object.fromEntries(
          parameters.map(({ name, value }) => [name, value]),
        ),
      }
      if (editing) await api.updateRunConfiguration(editing.id, payload)
      else await api.createRunConfiguration(projectId, payload)
      onSaved()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason : new Error())
      setAdvanced(true)
    } finally {
      busy.current = false
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      title={editing ? '编辑运行方案' : '新建运行方案'}
      initialFocusRef={commandInput}
      returnFocusRef={returnFocus}
      width="large"
      onClose={() => {
        if (!busy.current) onClose()
      }}
      footerButtons={[
        { content: '取消', disabled: submitting, onClick: onClose },
        {
          content: '保存运行方案',
          buttonType: 'primary',
          loading: submitting,
          disabled: submitting,
          onClick: () => void submit(),
        },
      ]}
    >
      <form
        ref={form}
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
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <fieldset className={styles.fields} disabled={submitting}>
          {error && (
            <Banner variant="critical">
              <Banner.Title>无法保存运行方案</Banner.Title>
              <Banner.Description>
                请检查配置与当前使用权限后重试。
                {error instanceof ApiError && error.problems.length > 0 && (
                  <ul>
                    {error.problems.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                )}
                {error instanceof ApiError && error.requestId && (
                  <p className={styles.muted}>请求标识：{error.requestId}</p>
                )}
              </Banner.Description>
            </Banner>
          )}
          <RunField disabled={submitting} label="方案名称" error={errors.name}>
            <TextInput
              block
              value={data.name}
              maxLength={128}
              aria-invalid={!!errors.name}
              onChange={(e) => patch({ name: e.target.value })}
            />
          </RunField>
          <RunField disabled={submitting} label="说明">
            <TextInput
              block
              value={data.description}
              onChange={(e) => patch({ description: e.target.value })}
            />
          </RunField>
          <RunField
            disabled={submitting}
            label="执行命令"
            required
            error={errors.command}
            caption="例如 python train.py 或 bash run.sh。Run 自动记录日志，不接收交互输入。"
          >
            <Textarea
              ref={commandInput}
              block
              rows={2}
              resize="vertical"
              className={styles.code}
              value={data.command}
              aria-invalid={!!errors.command}
              onChange={(e) => patch({ command: e.target.value })}
              placeholder="python train.py"
            />
          </RunField>
          <RunField
            disabled={submitting}
            label="运行环境"
            required
            error={errors.environment}
            caption="保存后固定使用所选环境版本。"
          >
            <Select
              block
              value={data.environment_version_id}
              onChange={(e) => patch({ environment_version_id: e.target.value })}
              aria-invalid={!!errors.environment}
            >
              <Select.Option value="" disabled hidden>
                请选择运行环境
              </Select.Option>
              {data.environment_version_id && !selectedVersion && (
                <Select.Option value={data.environment_version_id}>
                  已保存版本（当前不可用）
                </Select.Option>
              )}
              {versions.map(({ environment, version }) => (
                <Select.Option
                  key={version.id}
                  value={version.id}
                  disabled={version.availability !== 'available'}
                >
                  {environment.name} · {version.version}
                  {version.availability !== 'available' ? '（当前不可用）' : ''}
                </Select.Option>
              ))}
            </Select>
          </RunField>
          {data.environment_version_id &&
            (!selectedVersion || selectedVersion.version.availability !== 'available') && (
              <Banner variant="warning">
                <Banner.Title>原环境版本当前不可用</Banner.Title>
                <Banner.Description>
                  请确认使用权限或选择其他版本；原引用不会自动替换。
                </Banner.Description>
              </Banner>
            )}
          <RunField
            disabled={submitting}
            label="算力方案"
            required
            error={errors.compute}
            caption={
              plan
                ? describeComputeRequest(custom ? request : defaults(plan))
                : '选择平台提供的算力方案。'
            }
          >
            <Select
              block
              value={data.compute_plan_id}
              aria-invalid={!!errors.compute}
              onChange={(e) => {
                patch({ compute_plan_id: e.target.value })
                if (!custom) setRequest(defaults(plans.find((p) => p.id === e.target.value)))
              }}
            >
              <Select.Option value="" disabled hidden>
                请选择算力方案
              </Select.Option>
              {data.compute_plan_id && !plan && (
                <Select.Option value={data.compute_plan_id}>已保存方案（当前不可用）</Select.Option>
              )}
              {plans.map((p) => (
                <Select.Option key={p.id} value={p.id}>
                  {p.name}
                </Select.Option>
              ))}
            </Select>
          </RunField>
          <details
            className={styles.disclosure}
            open={resourcesOpen}
            onToggle={(e) => setResourcesOpen(e.currentTarget.open)}
          >
            <summary>调整资源{custom ? ' · 自定义数量' : ''}</summary>
            <div className={styles.grid}>
              {resourceFields.map(([key, label]) => (
                <RunField
                  disabled={submitting}
                  key={key}
                  label={label}
                  caption={plan ? `上限 ${plan[`max_${key}`]}` : undefined}
                  error={errors[`resource_${key}`]}
                >
                  <TextInput
                    block
                    type="number"
                    min={key === 'gpus' ? 0 : 1}
                    max={plan?.[`max_${key}`]}
                    value={request[key]}
                    aria-invalid={!!errors[`resource_${key}`]}

                    onChange={(e) => {
                      setCustom(true)
                      setRequest((old) => ({ ...old, [key]: Number(e.target.value) }))
                    }}
                  />
                </RunField>
              ))}
            </div>
            <div className={`${styles.row} ${styles.resourceActions}`}>
              <Button
                disabled={!plan}
                onClick={() => {
                  setCustom(false)
                  setRequest(defaults(plan))
                  setResourcesOpen(false)
                }}
              >
                恢复方案默认值
              </Button>
              <span className={styles.muted}>数量按当前算力方案范围校验。</span>
            </div>
          </details>
          <details
            className={styles.disclosure}
            open={outputs}
            onToggle={(e) => setOutputs(e.currentTarget.open)}
          >
            <summary>
              运行产物 ·{' '}
              {rules.length
                ? rules
                    .map((r) => `${r.path || '未填写'}${r.optional ? '（可选）' : ''}`)
                    .join('、')
                : '不收集'}
            </summary>
            <div className={styles.section}>
              <p className={styles.muted}>
                路径相对于工作目录。可选路径未生成时不影响 Run 结果。日志由平台单独记录。
              </p>
              {rules.map((rule, i) => (
                <div className={`${styles.item} ${styles.section}`} key={i}>
                  <RunField
                    disabled={submitting}
                    label={`产物路径 ${i + 1}`}
                    error={errors.outputs}
                  >
                    <TextInput
                      block
                      value={rule.path}
                      aria-invalid={!!errors.outputs}
                      onChange={(e) =>
                        patch({
                          artifact_rules: rules.map((r, j) =>
                            j === i ? { ...r, path: e.target.value } : r,
                          ),
                        })
                      }
                    />
                  </RunField>
                  <RunField disabled={submitting} label={`产物名称 ${i + 1}`}>
                    <TextInput
                      block
                      value={rule.name}
                      onChange={(e) =>
                        patch({
                          artifact_rules: rules.map((r, j) =>
                            j === i ? { ...r, name: e.target.value } : r,
                          ),
                        })
                      }
                    />
                  </RunField>
                  <label className={styles.row}>
                    <Checkbox
                      checked={rule.optional}
                      onChange={(e) =>
                        patch({
                          artifact_rules: rules.map((r, j) =>
                            j === i ? { ...r, optional: e.target.checked } : r,
                          ),
                        })
                      }
                    />
                    未生成时不影响 Run 结果
                  </label>
                  <div>
                    <Button
                      variant="danger"
                      aria-label={`删除产物规则 ${i + 1}`}
                      onClick={() => patch({ artifact_rules: rules.filter((_, j) => j !== i) })}
                    >
                      删除产物规则
                    </Button>
                  </div>
                </div>
              ))}
              <div>
                <Button
                  onClick={() =>
                    patch({ artifact_rules: [...rules, { path: '', name: '', optional: true }] })
                  }
                >
                  添加产物规则
                </Button>
              </div>
            </div>
          </details>
          <details
            className={styles.disclosure}
            open={advanced}
            onToggle={(e) => setAdvanced(e.currentTarget.open)}
          >
            <summary>
              高级设置
              {bindings.length || parameters.length || data.working_directory !== '.'
                ? ` · ${bindings.length} 项输入 · ${parameters.length} 项参数${data.working_directory !== '.' ? ' · 自定义工作目录' : ''}`
                : ''}
            </summary>
            <div className={styles.form}>
              {advanced && (
                <SharedResourceInputBindings
                  bindings={bindings}
                  onChange={(input_bindings) => patch({ input_bindings })}
                />
              )}
              {errors.inputs && <p role="alert">{errors.inputs}</p>}
              <section className={styles.section} aria-label="参数">
                <h3 className={styles.subheading}>参数</h3>
                <p className={styles.muted}>
                  值可使用普通文本、{'${{ vars.NAME }}'} 或 {'${{ secrets.NAME }}'}。个人引用使用{' '}
                  {'${{ user.vars.NAME }}'} / {'${{ user.secrets.NAME }}'}。
                </p>
                {parameters.map((row, i) => (
                  <div className={`${styles.item} ${styles.section}`} key={i}>
                    <RunField
                      disabled={submitting}
                      label={`参数名称 ${i + 1}`}
                      error={errors.parameters}
                    >
                      <TextInput
                        block
                        value={row.name}
                        aria-invalid={!!errors.parameters}
                        onChange={(e) =>
                          setParameters((old) =>
                            old.map((r, j) => (j === i ? { ...r, name: e.target.value } : r)),
                          )
                        }
                      />
                    </RunField>
                    <RunField disabled={submitting} label={`参数值 ${i + 1}`}>
                      <TextInput
                        block
                        value={row.value}
                        onChange={(e) =>
                          setParameters((old) =>
                            old.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)),
                          )
                        }
                      />
                    </RunField>
                    <div>
                      <Button
                        variant="danger"
                        aria-label={`删除参数 ${i + 1}`}
                        onClick={() => setParameters((old) => old.filter((_, j) => j !== i))}
                      >
                        删除参数
                      </Button>
                    </div>
                  </div>
                ))}
                <div>
                  <Button onClick={() => setParameters((old) => [...old, { name: '', value: '' }])}>
                    添加参数
                  </Button>
                </div>
              </section>
              <RunField
                disabled={submitting}
                label="工作目录"
                error={errors.work}
                caption="相对于 Project 根目录，默认 ."
              >
                <TextInput
                  block
                  value={data.working_directory}
                  aria-invalid={!!errors.work}
                  onChange={(e) => patch({ working_directory: e.target.value })}
                />
              </RunField>
            </div>
          </details>
        </fieldset>
      </form>
    </Dialog>
  )
}

const resourceFields = [
  ['cpus', 'CPU 核数'],
  ['memory_mb', '内存（MB）'],
  ['gpus', 'GPU 数量'],
  ['time_limit_minutes', '最长运行时间（分钟）'],
  ['nodes', '节点数'],
] as const
