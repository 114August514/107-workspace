import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Checkbox,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Typography,
  message,
} from 'antd'
import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type {
  ComputePlan,
  Environment,
  RunConfiguration,
  RunConfigurationInput,
} from '../../api/types'

interface Props {
  open: boolean
  projectId: string
  plans: ComputePlan[]
  environments: Environment[]
  /** 传入表示编辑，不传表示新建。 */
  editing?: RunConfiguration | null
  onClose: () => void
  onSaved: () => void
}

interface EnvRow {
  name: string
  value: string
}

interface RuleRow {
  path: string
  name: string
  optional: boolean
}

interface FormValues {
  name: string
  description: string
  command: string
  working_directory: string
  compute_plan_id: string
  environment_version_id?: string
  use_custom_resources: boolean
  nodes: number
  cpus: number
  memory_mb: number
  gpus: number
  time_limit_minutes: number
  env: EnvRow[]
  rules: RuleRow[]
}

export function RunConfigurationModal({
  open,
  projectId,
  plans,
  environments,
  editing,
  onClose,
  onSaved,
}: Props) {
  const [form] = Form.useForm<FormValues>()
  const [submitting, setSubmitting] = useState(false)
  const planId = Form.useWatch('compute_plan_id', form)
  const custom = Form.useWatch('use_custom_resources', form)
  const environmentVersionId = Form.useWatch('environment_version_id', form)
  const selectedEnvironmentVersion = environments
    .flatMap((environment) => environment.versions.map((version) => ({ environment, version })))
    .find(({ version }) => version.id === environmentVersionId)
  const plan = plans.find((item) => item.id === planId)

  useEffect(() => {
    if (!open) return
    const fallbackPlan = plans[0]
    const request = editing?.compute_request
    const source = plans.find((item) => item.id === editing?.compute_plan_id) ?? fallbackPlan
    form.setFieldsValue({
      name: editing?.name ?? '默认运行',
      description: editing?.description ?? '',
      command: editing?.command ?? '',
      working_directory: editing?.working_directory ?? '.',
      compute_plan_id: editing?.compute_plan_id ?? fallbackPlan?.id ?? '',
      environment_version_id: editing?.environment_version_id ?? undefined,
      use_custom_resources: Boolean(request),
      nodes: request?.nodes ?? source?.default_nodes ?? 1,
      cpus: request?.cpus ?? source?.default_cpus ?? 1,
      memory_mb: request?.memory_mb ?? source?.default_memory_mb ?? 1024,
      gpus: request?.gpus ?? source?.default_gpus ?? 0,
      time_limit_minutes: request?.time_limit_minutes ?? source?.default_time_limit_minutes ?? 30,
      env: Object.entries(editing?.environment_variables ?? {}).map(([name, value]) => ({
        name,
        value,
      })),
      rules: (editing?.artifact_rules ?? []).map((rule) => ({
        path: rule.path,
        name: rule.name,
        optional: rule.optional,
      })),
    })
  }, [open, editing, plans, form])

  /** 切换算力方案时，把资源数值重置成新方案的默认值。 */
  const applyPlanDefaults = (nextPlanId: string) => {
    const next = plans.find((item) => item.id === nextPlanId)
    if (!next) return
    form.setFieldsValue({
      nodes: next.default_nodes,
      cpus: next.default_cpus,
      memory_mb: next.default_memory_mb,
      gpus: next.default_gpus,
      time_limit_minutes: next.default_time_limit_minutes,
    })
  }

  const submit = async () => {
    const values = await form.validateFields()
    const payload: RunConfigurationInput = {
      name: values.name,
      description: values.description ?? '',
      command: values.command,
      working_directory: values.working_directory || '.',
      compute_plan_id: values.compute_plan_id,
      environment_version_id: values.environment_version_id ?? '',
      environment_variables: Object.fromEntries(
        (values.env ?? []).filter((row) => row?.name).map((row) => [row.name, row.value ?? '']),
      ),
      artifact_rules: (values.rules ?? [])
        .filter((row) => row?.path)
        .map((row) => ({ path: row.path, name: row.name ?? '', optional: row.optional ?? true })),
      // 这个弹窗不管输入绑定，但 PUT 是整体替换——不带上就等于清空。
      // 编辑一次名称就把 Artifact 输入全丢了，而且没有任何提示。
      // **表单没管的字段，提交时要原样带回去。**
      input_bindings: editing?.input_bindings ?? [],
      compute_request: values.use_custom_resources
        ? {
            nodes: values.nodes,
            cpus: values.cpus,
            memory_mb: values.memory_mb,
            gpus: values.gpus,
            time_limit_minutes: values.time_limit_minutes,
          }
        : null,
    }

    setSubmitting(true)
    try {
      if (editing) {
        await api.updateRunConfiguration(editing.id, payload)
        message.success('已更新运行方案')
      } else {
        await api.createRunConfiguration(projectId, payload)
        message.success('已创建运行方案')
      }
      onSaved()
      onClose()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const environmentOptions = environments.map((environment) => ({
    label: `${environment.name} · Owner ${environment.owner.display_name}`,
    options: environment.versions.map((version) => ({
      value: version.id,
      label: `${version.version} · ${version.available ? '可用' : '当前不可用'}`,
      disabled: !version.available,
    })),
  }))

  return (
    <Modal
      open={open}
      width={760}
      title={editing ? '编辑运行方案' : '新建运行方案'}
      okText="保存"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" requiredMark="optional">
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="name"
              label="方案名称"
              rules={[{ required: true, message: '请填写名称' }]}
            >
              <Input placeholder="默认运行" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="working_directory" label="工作目录" extra="相对于 Project 根目录">
              <Input placeholder="." />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item
          name="command"
          label="执行命令"
          rules={[{ required: true, message: '请填写执行命令' }]}
          extra="平台会把它写进作业脚本，你不需要自己写 sbatch"
        >
          <Input.TextArea rows={2} placeholder="python train.py" />
        </Form.Item>

        <Form.Item name="description" label="说明">
          <Input placeholder="这个方案用在什么场景" />
        </Form.Item>

        {environmentVersionId && !selectedEnvironmentVersion ? (
          <Alert
            type="warning"
            showIcon
            message="已保存的 Environment Version 当前无 USE 资格或已删除"
            description="运行方案仍保留原 exact version ID，不会自动切换。请选择一个当前可用版本后再保存。"
          />
        ) : selectedEnvironmentVersion && !selectedEnvironmentVersion.version.available ? (
          <Alert
            type="warning"
            showIcon
            message="已保存的 Environment Version 当前不可用"
            description="运行方案仍保留原 exact version ID，不会自动切换。请选择一个当前可用版本后再保存。"
          />
        ) : null}

        <Form.Item
          name="environment_version_id"
          label="Environment Version"
          rules={[{ required: true, message: '请选择 Environment Version' }]}
          extra="保存后固定引用这个版本；默认值变化、版本不可用或 USE Grant 撤销都不会静默切换"
        >
          <Select placeholder="选择确定的 Environment Version" options={environmentOptions} />
        </Form.Item>

        <Form.Item
          name="compute_plan_id"
          label="算力方案"
          rules={[{ required: true, message: '请选择算力方案' }]}
        >
          <Select
            onChange={applyPlanDefaults}
            options={plans.map((item) => ({
              value: item.id,
              label: `${item.name}（${item.code}）`,
            }))}
          />
        </Form.Item>

        <Form.Item name="use_custom_resources" valuePropName="checked">
          <Checkbox>自定义资源数量（不勾选则使用方案默认值）</Checkbox>
        </Form.Item>

        {custom && plan && (
          <>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`「${plan.name}」上限：${plan.max_nodes} 节点 / ${plan.max_cpus} 核 / ${plan.max_memory_mb} MB / ${plan.max_gpus} 张 GPU / ${plan.max_time_limit_minutes} 分钟`}
            />
            <Row gutter={12}>
              <Col span={4}>
                <Form.Item name="nodes" label="节点">
                  <InputNumber min={1} max={plan.max_nodes} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={5}>
                <Form.Item name="cpus" label="CPU 核">
                  <InputNumber min={1} max={plan.max_cpus} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={5}>
                <Form.Item name="memory_mb" label="内存 (MB)">
                  <InputNumber min={256} max={plan.max_memory_mb} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="gpus" label="GPU">
                  <InputNumber min={0} max={plan.max_gpus} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item name="time_limit_minutes" label="时限 (分钟)">
                  <InputNumber
                    min={1}
                    max={plan.max_time_limit_minutes}
                    style={{ width: '100%' }}
                  />
                </Form.Item>
              </Col>
            </Row>
          </>
        )}

        <Typography.Title level={5}>环境变量</Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
          值可以是字面量，也可以用 <Typography.Text code>{'${{ vars.NAME }}'}</Typography.Text> 或{' '}
          <Typography.Text code>{'${{ secrets.NAME }}'}</Typography.Text> 引用 Project / Project
          Owner scope；发起 User 配置使用显式 user namespace。
        </Typography.Paragraph>
        <Form.List name="env">
          {(fields, { add, remove }) => (
            <Space direction="vertical" style={{ width: '100%' }}>
              {fields.map((field) => (
                <Space key={field.key} align="baseline" style={{ width: '100%' }}>
                  <Form.Item name={[field.name, 'name']} style={{ marginBottom: 8 }}>
                    <Input placeholder="EPOCHS" style={{ width: 220 }} />
                  </Form.Item>
                  <Form.Item name={[field.name, 'value']} style={{ marginBottom: 8 }}>
                    <Input placeholder="5 或 ${{ vars.EPOCHS }}" style={{ width: 340 }} />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(field.name)} />
                </Space>
              ))}
              <Button
                type="dashed"
                onClick={() => add({ name: '', value: '' })}
                icon={<PlusOutlined />}
              >
                添加环境变量
              </Button>
            </Space>
          )}
        </Form.List>

        <Typography.Title level={5} style={{ marginTop: 24 }}>
          Artifact 收集规则
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
          Run 结束后，这些路径会被保存为 Artifact。路径相对于工作目录。
        </Typography.Paragraph>
        <Form.List name="rules">
          {(fields, { add, remove }) => (
            <Space direction="vertical" style={{ width: '100%' }}>
              {fields.map((field) => (
                <Space key={field.key} align="baseline" style={{ width: '100%' }}>
                  <Form.Item name={[field.name, 'path']} style={{ marginBottom: 8 }}>
                    <Input placeholder="outputs" style={{ width: 220 }} />
                  </Form.Item>
                  <Form.Item name={[field.name, 'name']} style={{ marginBottom: 8 }}>
                    <Input placeholder="展示名称（可选）" style={{ width: 240 }} />
                  </Form.Item>
                  <Form.Item
                    name={[field.name, 'optional']}
                    valuePropName="checked"
                    style={{ marginBottom: 8 }}
                  >
                    <Checkbox>可选</Checkbox>
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(field.name)} />
                </Space>
              ))}
              <Button
                type="dashed"
                onClick={() => add({ path: '', name: '', optional: true })}
                icon={<PlusOutlined />}
              >
                添加收集规则
              </Button>
            </Space>
          )}
        </Form.List>
      </Form>
    </Modal>
  )
}
