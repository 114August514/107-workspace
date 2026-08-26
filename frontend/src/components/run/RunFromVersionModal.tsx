import {
  Alert,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, api, newIdempotencyKey } from '../../api/client'
import type { PreflightResult, Run, RunConfiguration } from '../../api/types'
import { describeComputeRequest } from '../../utils/format'

interface Props {
  open: boolean
  versionId: string
  versionLabel: string
  projectId: string
  defaultRunConfigurationId: string | null
  onClose: () => void
  onSubmitted: (run: Run) => void
}

/**
 * 从指定 Version 发起 Run。
 *
 * 与 SubmitRunModal 的关键差异：RunDraft 中显式传入 project_version_id，
 * 而非省略让后端默认取最新版本。这确保 Run 绑定用户选择的确定版本，
 * 而不是「提交那一刻」的最新快照。
 */
export function RunFromVersionModal({
  open,
  versionId,
  versionLabel,
  projectId,
  defaultRunConfigurationId,
  onClose,
  onSubmitted,
}: Props) {
  const [form] = Form.useForm<{ name: string; run_configuration_id: string }>()
  const [configurations, setConfigurations] = useState<RunConfiguration[]>([])
  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null)
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string[] | null>(null)
  const [loadingConfigs, setLoadingConfigs] = useState(false)
  const [idempotencyKey, setIdempotencyKey] = useState('')
  // 用于丢弃过期 Preflight 请求：只有最近一次请求能修改 preflight/error/checking
  const preflightRequestId = useRef(0)

  // 加载运行方案列表
  useEffect(() => {
    if (!open) return
    setLoadingConfigs(true)
    api
      .listRunConfigurations(projectId)
      .then((configs) => {
        setConfigurations(configs)
        // 默认选择：优先匹配 defaultRunConfigurationId，否则选第一个
        const defaultConfig = configs.find((c) => c.id === defaultRunConfigurationId) ?? configs[0]
        if (defaultConfig) {
          setSelectedConfigId(defaultConfig.id)
          form.setFieldsValue({ run_configuration_id: defaultConfig.id })
        } else {
          setSelectedConfigId(null)
        }
      })
      .catch((exc) => setError([(exc as Error).message]))
      .finally(() => setLoadingConfigs(false))
  }, [open, projectId, defaultRunConfigurationId, form])

  // Preflight：选中 configuration 后调用
  const runPreflight = useCallback(async () => {
    if (!selectedConfigId) return
    // 递增序列号，标记这次是「最新」请求；旧请求返回时据此丢弃自己
    const requestId = ++preflightRequestId.current
    setChecking(true)
    setError(null)
    // 立即清掉旧 Preflight，避免切换 config 时旧结果短暂残留
    setPreflight(null)
    try {
      const result = await api.preflight(projectId, {
        run_configuration_id: selectedConfigId,
        project_version_id: versionId,
      })
      if (requestId !== preflightRequestId.current) return
      setPreflight(result)
    } catch (exc) {
      if (requestId !== preflightRequestId.current) return
      setPreflight(null)
      setError(exc instanceof ApiError ? [exc.detail] : [(exc as Error).message])
    } finally {
      if (requestId === preflightRequestId.current) {
        setChecking(false)
      }
    }
  }, [selectedConfigId, projectId, versionId])

  useEffect(() => {
    if (open && selectedConfigId) {
      void runPreflight()
    }
  }, [open, selectedConfigId, runPreflight])

  // 打开时重置
  useEffect(() => {
    if (open) {
      form.resetFields()
      setIdempotencyKey(newIdempotencyKey())
      setPreflight(null)
      setError(null)
    }
  }, [open, form])

  const selectedConfig = configurations.find((c) => c.id === selectedConfigId) ?? null

  const submit = async () => {
    if (!selectedConfigId) return
    const values = await form.getFieldsValue()
    setSubmitting(true)
    setError(null)
    try {
      const run = await api.createRun(
        projectId,
        {
          run_configuration_id: selectedConfigId,
          project_version_id: versionId,
          name: values.name ?? '',
        },
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

  const noConfigs = configurations.length === 0 && !loadingConfigs

  return (
    <Modal
      open={open}
      width={680}
      title={`运行版本 ${versionLabel}`}
      okText="提交"
      cancelText="取消"
      okButtonProps={{ disabled: checking || !preflight?.ok || noConfigs }}
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

        {noConfigs && (
          <Alert
            type="warning"
            showIcon
            message="请先创建运行方案"
            description="这个 Project 还没有运行方案，无法提交 Run。"
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
          <Form.Item name="run_configuration_id" label="运行方案">
            <Select
              placeholder="选择运行方案"
              value={selectedConfigId ?? undefined}
              onChange={setSelectedConfigId}
              disabled={noConfigs}
              loading={loadingConfigs}
              options={configurations.map((c) => ({
                value: c.id,
                label: c.name,
              }))}
            />
          </Form.Item>
          <Form.Item name="name" label="Run 名称" extra="留空会自动生成">
            <Input placeholder={`例如：${versionLabel} 首次运行`} />
          </Form.Item>
        </Form>

        {selectedConfig && (
          <Descriptions
            size="small"
            column={1}
            bordered
            title="本次将要固定的执行配置"
            items={[
              {
                key: 'version',
                label: 'Project Version',
                children: versionLabel,
              },
              {
                key: 'command',
                label: '执行命令',
                children: <Typography.Text code>{selectedConfig.command}</Typography.Text>,
              },
              {
                key: 'workdir',
                label: '工作目录',
                children: selectedConfig.working_directory ?? '.',
              },
              {
                key: 'environment',
                label: '运行环境版本',
                children: preflight?.environment_version_id ?? (checking ? '检查中…' : '—'),
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
        )}

        {secretNames.length > 0 && (
          <Typography.Text type="secondary">
            Secret 的值不会出现在运行快照、日志和这个页面上，只在执行时注入作业进程。
          </Typography.Text>
        )}
      </Space>
    </Modal>
  )
}
