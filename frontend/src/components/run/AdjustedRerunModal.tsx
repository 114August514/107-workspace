import { Alert, Form, Input, InputNumber, Modal, Select, Space, Typography } from 'antd'
import { useEffect, useState } from 'react'

import { ApiError, api, newIdempotencyKey } from '../../api/client'
import type { ComputeRequest, InputBinding, Run, RunDetail } from '../../api/types'
import { describeComputeRequest } from '../../utils/format'

interface Props {
  open: boolean
  projectId: string
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

export function AdjustedRerunModal({ open, projectId, detail, onClose, onSubmitted }: Props) {
  const [form] = Form.useForm<FormValues>()
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [problems, setProblems] = useState<string[]>([])
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey)
  const snapshot = detail.snapshot

  useEffect(() => {
    if (!open) return
    form.setFieldsValue({
      name: detail.run.name,
      project_version_id: snapshot.project_version_id,
      environment_version_id: snapshot.environment_version_id,
      working_directory: snapshot.working_directory || '.',
      command: snapshot.command,
      input_bindings: snapshot.input_bindings,
      compute_request: snapshot.compute_request,
    })
    setProblems([])
    setIdempotencyKey(newIdempotencyKey())
  }, [detail.run.name, form, open, snapshot])

  const submit = async (values: FormValues) => {
    setChecking(true)
    setProblems([])
    try {
      if (snapshot.source_run_configuration_id) {
        const preflight = await api.preflight(projectId, {
          run_configuration_id: snapshot.source_run_configuration_id,
          project_version_id: values.project_version_id,
          command_override: values.command,
          working_directory_override: values.working_directory,
          environment_version_id_override: values.environment_version_id,
          input_bindings_override: values.input_bindings,
          compute_request_override: values.compute_request,
        })
        if (!preflight.ok) {
          setProblems(preflight.problems)
          return
        }
      }
      setSubmitting(true)
      const created = await api.adjustedRerun(
        detail.run.id,
        {
          name: values.name,
          project_version_id: values.project_version_id,
          environment_version_id: values.environment_version_id,
          working_directory: values.working_directory,
          command: values.command,
          input_bindings: values.input_bindings ?? [],
          compute_request: values.compute_request,
        },
        idempotencyKey,
      )
      onSubmitted(created)
    } catch (error) {
      const apiError = error instanceof ApiError ? error : undefined
      setProblems(
        apiError?.problems.length
          ? apiError.problems
          : [error instanceof Error ? error.message : '调整后重跑失败'],
      )
    } finally {
      setChecking(false)
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      title="调整后重新运行"
      okText="检查并创建新 Run"
      cancelText="取消"
      confirmLoading={checking || submitting}
      onCancel={onClose}
      onOk={() => void form.submit()}
      width={720}
    >
      <Typography.Paragraph type="secondary">
        以当前 Run Snapshot 为起点。提交会创建新的 Run，不会修改来源
        Run；环境、输入和算力权益按当前状态重新校验。
      </Typography.Paragraph>
      {problems.length > 0 ? (
        <Alert
          type="error"
          showIcon
          message="当前配置不能提交"
          description={
            <ul>
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item
          name="name"
          label="新 Run 名称"
          rules={[{ required: true, message: '请输入 Run 名称' }]}
        >
          <Input />
        </Form.Item>
        <Space.Compact block>
          <Form.Item
            name="project_version_id"
            label="Project Version"
            rules={[{ required: true }]}
            style={{ flex: 1 }}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="environment_version_id"
            label="Environment Version"
            rules={[{ required: true }]}
            style={{ flex: 1 }}
          >
            <Input />
          </Form.Item>
        </Space.Compact>
        <Form.Item
          name="command"
          label="执行命令"
          rules={[{ required: true, message: '请输入执行命令' }]}
        >
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="working_directory" label="工作目录" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Typography.Text strong>Compute Request</Typography.Text>
        <Space wrap style={{ display: 'flex', marginTop: 8 }}>
          {(['nodes', 'cpus', 'memory_mb', 'gpus', 'time_limit_minutes'] as const).map((field) => (
            <Form.Item
              key={field}
              name={['compute_request', field]}
              label={field}
              rules={[{ required: true }]}
            >
              <InputNumber min={0} />
            </Form.Item>
          ))}
        </Space>
        <Typography.Text strong>Input Binding</Typography.Text>
        <Form.List name="input_bindings">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Space key={key} align="start" style={{ display: 'flex', marginTop: 8 }}>
                  <Form.Item
                    {...restField}
                    name={[name, 'source_type']}
                    rules={[{ required: true }]}
                  >
                    <Select
                      style={{ width: 170 }}
                      options={[
                        { value: 'artifact', label: 'Artifact' },
                        { value: 'shared_resource_version', label: 'Shared Resource Version' },
                      ]}
                    />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'source_id']} rules={[{ required: true }]}>
                    <Input placeholder="source id" />
                  </Form.Item>
                  <Form.Item
                    {...restField}
                    name={[name, 'access_path']}
                    rules={[{ required: true }]}
                  >
                    <Input placeholder="/inputs/data" />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'source_subpath']}>
                    <Input placeholder="子路径（可选）" />
                  </Form.Item>
                  <a onClick={() => remove(name)}>删除</a>
                </Space>
              ))}
              <a
                onClick={() =>
                  add({
                    source_type: 'artifact',
                    source_id: '',
                    access_path: '/',
                    source_subpath: '',
                  })
                }
              >
                添加 Input Binding
              </a>
            </>
          )}
        </Form.List>
        <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
          当前请求：{describeComputeRequest(snapshot.compute_request)}；修改后以表单值为准。
        </Typography.Paragraph>
      </Form>
    </Modal>
  )
}
