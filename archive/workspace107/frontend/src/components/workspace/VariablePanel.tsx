import { Alert, Button, Form, Input, Popconfirm, Space, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { Variable, Workspace } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { AsyncSection } from '../common/AsyncSection'

/**
 * Workspace 配置变量与 Secret。
 *
 * 两者的界面刻意不同：Variable 的值可以看，Secret 只列名称——
 * 后端根本没有读取 Secret 值的接口（GR-012）。
 */
export function VariablePanel({ workspace }: { workspace: Workspace }) {
  const variables = useAsync<Variable[]>(() => api.listVariables(workspace.id), [workspace.id])
  const secrets = useAsync<string[]>(() => api.listSecretNames(workspace.id), [workspace.id])
  const [variableForm] = Form.useForm<Variable>()
  const [secretForm] = Form.useForm<{ name: string; value: string }>()
  const [busy, setBusy] = useState(false)
  const canManage = can(workspace, 'config.manage')

  const run = async (action: () => Promise<void>, onDone: () => void, success: string) => {
    setBusy(true)
    try {
      await action()
      message.success(success)
      onDone()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const saveVariable = async () => {
    const values = await variableForm.validateFields()
    await run(
      async () => {
        await api.setVariable(workspace.id, values.name, values.value)
      },
      () => {
        variableForm.resetFields()
        variables.reload()
      },
      '已保存配置变量',
    )
  }

  const saveSecret = async () => {
    const values = await secretForm.validateFields()
    await run(
      async () => {
        await api.setSecret(workspace.id, values.name, values.value)
      },
      () => {
        secretForm.resetFields()
        secrets.reload()
      },
      '已保存 Secret',
    )
  }

  const variableColumns: ColumnsType<Variable> = [
    { title: '名称', dataIndex: field<Variable>('name'), width: 220 },
    {
      title: '值',
      dataIndex: field<Variable>('value'),
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
    },
    {
      title: '在运行方案中引用',
      dataIndex: field<Variable>('name'),
      key: 'expression',
      render: (name: string) => (
        <Typography.Text copyable code>{`\${{ vars.${name} }}`}</Typography.Text>
      ),
    },
  ]

  if (canManage) {
    variableColumns.push({
      title: '操作',
      width: 90,
      key: 'actions',
      render: (_, variable) => (
        <Popconfirm
          title={`删除 ${variable.name}？`}
          okText="删除"
          cancelText="取消"
          onConfirm={() =>
            run(
              async () => {
                await api.deleteVariable(workspace.id, variable.name)
              },
              variables.reload,
              '已删除',
            )
          }
        >
          <Button type="link" danger size="small">
            删除
          </Button>
        </Popconfirm>
      ),
    })
  }

  const secretColumns: ColumnsType<string> = [
    { title: '名称', render: (name: string) => name, width: 220 },
    {
      title: '在运行方案中引用',
      key: 'expression',
      render: (name: string) => (
        <Typography.Text copyable code>{`\${{ secrets.${name} }}`}</Typography.Text>
      ),
    },
  ]

  if (canManage) {
    secretColumns.push({
      title: '操作',
      width: 90,
      key: 'actions',
      render: (name: string) => (
        <Popconfirm
          title={`删除 ${name}？`}
          okText="删除"
          cancelText="取消"
          onConfirm={() =>
            run(
              async () => {
                await api.deleteSecret(workspace.id, name)
              },
              secrets.reload,
              '已删除',
            )
          }
        >
          <Button type="link" danger size="small">
            删除
          </Button>
        </Popconfirm>
      ),
    })
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Typography.Title level={5}>配置变量</Typography.Title>
        {canManage && (
          <Form form={variableForm} layout="inline" style={{ marginBottom: 12 }}>
            <Form.Item name="name" rules={[{ required: true, message: '请填写名称' }]}>
              <Input placeholder="EPOCHS" style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="value" rules={[{ required: true, message: '请填写值' }]}>
              <Input placeholder="5" style={{ width: 240 }} />
            </Form.Item>
            <Form.Item>
              <Button onClick={saveVariable} loading={busy}>
                保存
              </Button>
            </Form.Item>
          </Form>
        )}
        <AsyncSection loading={variables.loading} error={variables.error}>
          <Table
            rowKey="name"
            size="small"
            dataSource={variables.data ?? []}
            columns={variableColumns}
            pagination={false}
          />
        </AsyncSection>
      </div>

      <div>
        <Typography.Title level={5}>Secret</Typography.Title>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="Secret 的值写入后无法再读出"
          description="平台不提供任何读取 Secret 值的接口。它只会在执行 Run 时注入到作业进程里，不会出现在运行快照、日志和页面上。"
        />
        {canManage && (
          <Form form={secretForm} layout="inline" style={{ marginBottom: 12 }}>
            <Form.Item name="name" rules={[{ required: true, message: '请填写名称' }]}>
              <Input placeholder="HF_TOKEN" style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="value" rules={[{ required: true, message: '请填写值' }]}>
              <Input.Password placeholder="粘贴 Token" style={{ width: 240 }} />
            </Form.Item>
            <Form.Item>
              <Button onClick={saveSecret} loading={busy}>
                保存
              </Button>
            </Form.Item>
          </Form>
        )}
        <AsyncSection loading={secrets.loading} error={secrets.error}>
          <Table
            rowKey={(name) => name}
            size="small"
            dataSource={secrets.data ?? []}
            columns={secretColumns}
            pagination={false}
          />
        </AsyncSection>
      </div>
    </Space>
  )
}
