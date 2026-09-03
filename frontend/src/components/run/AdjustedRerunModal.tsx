import { PlusIcon, TrashIcon } from '@primer/octicons-react'
import {
  Button,
  Dialog,
  Flash,
  FormControl,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@primer/react'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { api, newIdempotencyKey } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import type { ComputeRequest, InputBinding, Run, RunDetail } from '../../api/types'
import { describeComputeRequest } from '../../utils/format'
import styles from './run.module.css'

interface Props {
  open: boolean
  detail: RunDetail
  onClose: () => void
  onSubmitted: (run: Run) => void
}

type FormValues = {
  name: string
  project_version_id: string
  environment_version_id: string
  working_directory: string
  command: string
  input_bindings: InputBinding[]
  compute_request: ComputeRequest
}

function initialValues(detail: RunDetail): FormValues {
  return {
    name: detail.run.name,
    project_version_id: detail.snapshot.project_version_id,
    environment_version_id: detail.snapshot.environment_version_id,
    working_directory: detail.snapshot.working_directory || '.',
    command: detail.snapshot.command,
    input_bindings: detail.snapshot.input_bindings.map((binding) => ({ ...binding })),
    compute_request: { ...detail.snapshot.compute_request },
  }
}

export function AdjustedRerunModal({ open, detail, onClose, onSubmitted }: Props) {
  if (!open) return null
  return <AdjustedRerunForm detail={detail} onClose={onClose} onSubmitted={onSubmitted} />
}

function AdjustedRerunForm({ detail, onClose, onSubmitted }: Omit<Props, 'open'>) {
  const formRef = useRef<HTMLFormElement>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const [values, setValues] = useState(() => initialValues(detail))
  const [submitting, setSubmitting] = useState(false)
  const [problems, setProblems] = useState<string[]>([])
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey)

  useEffect(() => {
    const next = initialValues(detail)
    setValues(next)
    setProblems([])
    setIdempotencyKey(newIdempotencyKey())
  }, [detail])

  const update = <K extends keyof FormValues>(field: K, value: FormValues[K]) => {
    setValues((current) => ({ ...current, [field]: value }))
  }

  const updateBinding = (index: number, patch: Partial<InputBinding>) => {
    setValues((current) => ({
      ...current,
      input_bindings: current.input_bindings.map((binding, itemIndex) =>
        itemIndex === index ? { ...binding, ...patch } : binding,
      ),
    }))
  }

  const updateRequest = <K extends keyof ComputeRequest>(field: K, value: number) => {
    setValues((current) => ({
      ...current,
      compute_request: { ...current.compute_request, [field]: value },
    }))
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextProblems: string[] = []
    if (!values.name.trim()) nextProblems.push('请输入新 Run 名称')
    if (!values.project_version_id.trim()) nextProblems.push('请输入 Project Version ID')
    if (!values.environment_version_id.trim()) nextProblems.push('请输入 Environment Version ID')
    if (!values.command.trim()) nextProblems.push('请输入执行命令')
    if (!values.working_directory.trim()) nextProblems.push('请输入工作目录')
    if (nextProblems.length > 0) {
      setProblems(nextProblems)
      nameRef.current?.focus()
      return
    }

    setSubmitting(true)
    setProblems([])
    try {
      const created = await api.adjustedRerun(
        detail.run.id,
        {
          name: values.name.trim(),
          project_version_id: values.project_version_id.trim(),
          environment_version_id: values.environment_version_id.trim(),
          working_directory: values.working_directory.trim(),
          command: values.command.trim(),
          input_bindings: values.input_bindings,
          compute_request: values.compute_request,
        },
        idempotencyKey,
      )
      onSubmitted(created)
    } catch (error) {
      const view = toAsyncError(error as Error)
      setProblems(view?.problems?.length ? view.problems : [view?.message ?? '调整后重跑失败'])
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      title="调整后重新运行"
      width="large"
      initialFocusRef={nameRef}
      onClose={() => {
        if (!submitting) onClose()
      }}
      footerButtons={[
        { content: '取消', disabled: submitting, onClick: onClose },
        {
          content: '创建新 Run',
          buttonType: 'primary',
          loading: submitting,
          disabled: submitting,
          onClick: () => formRef.current?.requestSubmit(),
        },
      ]}
    >
      <form ref={formRef} id="adjusted-rerun-form" onSubmit={submit}>
        <Stack gap="normal">
          <Text as="p" className={styles.muted}>
            以当前 Run Snapshot 为起点。提交会创建新的 Run，不会修改来源
            Run；环境、输入和算力权益按当前状态重新校验。
          </Text>
          {problems.length > 0 ? (
            <Flash variant="danger" role="alert">
              <strong>当前配置不能提交</strong>
              <ul className={styles.adjustedRerunProblems}>
                {problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </Flash>
          ) : null}
          <FormControl required disabled={submitting} id="adjusted-rerun-name">
            <FormControl.Label>新 Run 名称</FormControl.Label>
            <TextInput
              ref={nameRef}
              value={values.name}
              maxLength={255}
              block
              onChange={(event) => update('name', event.target.value)}
            />
          </FormControl>
          <div className={styles.adjustedRerunGrid}>
            <FormControl required disabled={submitting} id="adjusted-rerun-project-version">
              <FormControl.Label>Project Version ID</FormControl.Label>
              <TextInput
                value={values.project_version_id}
                block
                onChange={(event) => update('project_version_id', event.target.value)}
              />
            </FormControl>
            <FormControl required disabled={submitting} id="adjusted-rerun-environment-version">
              <FormControl.Label>Environment Version ID</FormControl.Label>
              <TextInput
                value={values.environment_version_id}
                block
                onChange={(event) => update('environment_version_id', event.target.value)}
              />
            </FormControl>
          </div>
          <FormControl required disabled={submitting} id="adjusted-rerun-command">
            <FormControl.Label>执行命令</FormControl.Label>
            <Textarea
              value={values.command}
              rows={3}
              block
              resize="vertical"
              onChange={(event) => update('command', event.target.value)}
            />
          </FormControl>
          <FormControl required disabled={submitting} id="adjusted-rerun-working-directory">
            <FormControl.Label>工作目录</FormControl.Label>
            <TextInput
              value={values.working_directory}
              block
              onChange={(event) => update('working_directory', event.target.value)}
            />
            <FormControl.Caption>相对于 Project Version 根目录。</FormControl.Caption>
          </FormControl>
          <section aria-labelledby="adjusted-rerun-compute-title">
            <Text id="adjusted-rerun-compute-title" as="h3" weight="semibold">
              Compute Request
            </Text>
            <div className={styles.adjustedRerunComputeGrid}>
              {(['nodes', 'cpus', 'memory_mb', 'gpus', 'time_limit_minutes'] as const).map(
                (field) => (
                  <FormControl key={field} disabled={submitting} id={`adjusted-rerun-${field}`}>
                    <FormControl.Label>{field}</FormControl.Label>
                    <TextInput
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={String(values.compute_request[field])}
                      onChange={(event) => updateRequest(field, Number(event.target.value))}
                    />
                  </FormControl>
                ),
              )}
            </div>
            <Text as="p" className={styles.muted}>
              当前请求：{describeComputeRequest(detail.snapshot.compute_request)}
              ；修改后以表单值为准。
            </Text>
          </section>
          <section aria-labelledby="adjusted-rerun-input-title">
            <Text id="adjusted-rerun-input-title" as="h3" weight="semibold">
              Input Binding
            </Text>
            <Stack gap="condensed">
              {values.input_bindings.map((binding, index) => (
                <div className={styles.adjustedRerunBinding} key={`${binding.source_id}-${index}`}>
                  <FormControl disabled={submitting} id={`adjusted-rerun-binding-type-${index}`}>
                    <FormControl.Label>来源类型</FormControl.Label>
                    <Select
                      value={binding.source_type}
                      onChange={(event) =>
                        updateBinding(index, {
                          source_type: event.target.value as InputBinding['source_type'],
                        })
                      }
                    >
                      <Select.Option value="artifact">Artifact</Select.Option>
                      <Select.Option value="shared_resource_version">
                        Shared Resource Version
                      </Select.Option>
                    </Select>
                  </FormControl>
                  <FormControl
                    required
                    disabled={submitting}
                    id={`adjusted-rerun-binding-source-${index}`}
                  >
                    <FormControl.Label>来源 ID</FormControl.Label>
                    <TextInput
                      value={binding.source_id}
                      block
                      onChange={(event) => updateBinding(index, { source_id: event.target.value })}
                    />
                  </FormControl>
                  <FormControl
                    required
                    disabled={submitting}
                    id={`adjusted-rerun-binding-access-${index}`}
                  >
                    <FormControl.Label>访问路径</FormControl.Label>
                    <TextInput
                      value={binding.access_path}
                      block
                      onChange={(event) =>
                        updateBinding(index, { access_path: event.target.value })
                      }
                    />
                  </FormControl>
                  <FormControl disabled={submitting} id={`adjusted-rerun-binding-subpath-${index}`}>
                    <FormControl.Label>来源子路径</FormControl.Label>
                    <TextInput
                      value={binding.source_subpath}
                      block
                      onChange={(event) =>
                        updateBinding(index, { source_subpath: event.target.value })
                      }
                    />
                  </FormControl>
                  <Button
                    leadingVisual={TrashIcon}
                    variant="invisible"
                    disabled={submitting}
                    onClick={() =>
                      update(
                        'input_bindings',
                        values.input_bindings.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                  >
                    删除
                  </Button>
                </div>
              ))}
              <Button
                leadingVisual={PlusIcon}
                variant="default"
                size="small"
                disabled={submitting}
                onClick={() =>
                  update('input_bindings', [
                    ...values.input_bindings,
                    {
                      source_type: 'artifact',
                      source_id: '',
                      access_path: '/inputs/data',
                      source_subpath: '',
                    },
                  ])
                }
              >
                添加 Input Binding
              </Button>
            </Stack>
          </section>
        </Stack>
      </form>
    </Dialog>
  )
}
