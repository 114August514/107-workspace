import { Alert, Descriptions, Form, Input, Modal, Space, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'

import { ApiError, api, newIdempotencyKey } from '../../api/client'
import type { PreflightResult, Run, RunConfiguration } from '../../api/types'
import { describeComputeRequest } from '../../utils/format'

interface Props {
  open: boolean
  projectId: string
  configuration: RunConfiguration | null
  onClose: () => void
  onSubmitted: (run: Run) => void
}

/**
 * 提交 Run。
 *
 * 打开时先跑一次提交前检查，把所有阻止提交的问题一次性列出来，
 * 而不是让用户点了「提交」再一条条试。
 */
export function SubmitRunModal({ open, projectId, configuration, onClose, onSubmitted }: Props) {
  const [form] = Form.useForm<{ name: string }>()
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string[] | null>(null)
  // 打开弹窗 = 形成一次提交意图。这之后无论点几次「提交」、
  // 或者失败后重试，都是同一个意图，用同一个键。
  const [idempotencyKey, setIdempotencyKey] = useState('')

  const runPreflight = useCallback(async () => {
    if (!configuration) return
    setChecking(true)
    setError(null)
    try {
      setPreflight(await api.preflight(projectId, { run_configuration_id: configuration.id }))
    } catch (exc) {
      setPreflight(null)
      setError(exc instanceof ApiError ? [exc.detail] : [(exc as Error).message])
    } finally {
      setChecking(false)
    }
  }, [configuration, projectId])

  useEffect(() => {
    if (open) {
      form.resetFields()
      setIdempotencyKey(newIdempotencyKey())
      void runPreflight()
    }
  }, [open, runPreflight, form])

  const submit = async () => {
    if (!configuration) return
    const values = await form.getFieldsValue()
    setSubmitting(true)
    setError(null)
    try {
      const run = await api.createRun(
        projectId,
        { run_configuration_id: configuration.id, name: values.name ?? '' },
        idempotencyKey,
      )
      message.success('已提交 Run')
      onSubmitted(run)
      onClose()
    } catch (exc) {
      setError(
        exc instanceof ApiError && exc.problems.length > 0
          ? exc.problems
          : [(exc as Error).message],
      )
    } finally {
      setSubmitting(false)
    }
  }

  const secretNames = Object.entries(preflight?.secret_references ?? {})
  const literalNames = Object.entries(preflight?.resolved_environment_variables ?? {})

  return (
    <Modal
      open={open}
      width={680}
      title={`提交 Run · ${configuration?.name ?? ''}`}
      okText="提交"
      cancelText="取消"
      okButtonProps={{ disabled: !preflight?.ok }}
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {error && (
          <Alert
            type="error"
            showIcon
            message="提交失败"
            description={
              <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                {error.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            }
          />
        )}

        {preflight && !preflight.ok && (
          <Alert
            type="warning"
            showIcon
            message="提交前检查没有通过"
            description={
              <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                {preflight.problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            }
          />
        )}

        {preflight?.ok && <Alert type="success" showIcon message="提交前检查通过" />}

        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Run 名称" extra="留空会自动生成">
            <Input placeholder="例如：baseline 第一次" />
          </Form.Item>
        </Form>

        <Descriptions
          size="small"
          column={1}
          bordered
          title="本次将要固定的执行配置"
          items={[
            {
              key: 'command',
              label: '执行命令',
              children: <Typography.Text code>{configuration?.command}</Typography.Text>,
            },
            {
              key: 'workdir',
              label: '工作目录',
              children: configuration?.working_directory ?? '.',
            },
            {
              key: 'version',
              label: 'Project Version',
              children: preflight?.project_version_id ?? (checking ? '检查中…' : '—'),
            },
            {
              key: 'environment',
              label: 'Environment Version',
              children: checking ? (
                '检查中…'
              ) : preflight?.environment_version ? (
                <Space wrap size={6}>
                  <Typography.Text>{preflight.environment_version.version}</Typography.Text>
                  <Tag
                    color={
                      preflight.environment_version.availability === 'available'
                        ? 'green'
                        : 'orange'
                    }
                  >
                    {preflight.environment_version.availability === 'available'
                      ? '当前可用'
                      : '当前不可用'}
                  </Tag>
                  <Typography.Text code>{preflight.environment_version.id}</Typography.Text>
                </Space>
              ) : (
                <Typography.Text code>
                  {configuration?.environment_version_id ?? '—'}
                </Typography.Text>
              ),
            },
            {
              key: 'compute',
              label: '算力请求',
              children: preflight?.compute_request
                ? describeComputeRequest(preflight.compute_request)
                : '—',
            },
            {
              key: 'env',
              label: '环境变量',
              children:
                literalNames.length + secretNames.length === 0 ? (
                  '—'
                ) : (
                  <Space direction="vertical" size={4}>
                    {literalNames.map(([name, value]) => (
                      <Typography.Text key={name} code>{`${name}=${value}`}</Typography.Text>
                    ))}
                    {secretNames.map(([name, secret]) => (
                      <Space key={name} size={6}>
                        <Typography.Text code>{name}</Typography.Text>
                        <Tag color="purple">来自 Secret {secret}</Tag>
                      </Space>
                    ))}
                  </Space>
                ),
            },
          ]}
        />

        {secretNames.length > 0 && (
          <Typography.Text type="secondary">
            Secret 的值不会出现在运行快照、日志和这个页面上，只在执行时注入作业进程。
          </Typography.Text>
        )}
      </Space>
    </Modal>
  )
}
