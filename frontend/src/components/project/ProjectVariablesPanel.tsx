import { PlusOutlined } from '@ant-design/icons'
import { Button, Form, Input, Modal, Popconfirm, Space, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { Project } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncSection } from '../common/AsyncSection'

interface Props {
  projectId: string
  access: Project | undefined
  onChanged?: () => void
}

interface VariableFormValues {
  name: string
  value: string
}

/**
 * Project Variable 管理（Issue #54）。
 *
 * 自包含面板：只依赖 projectId 与 access，#86 的 Settings 路由可直接挂载。
 * 解析语义由后端 contract 决定，前端只做 CRUD 入口。
 */
export function ProjectVariablesPanel({ projectId, access, onChanged }: Props) {
  const canManage = can(access, 'config.manage')
  const variables = useAsync<{ name: string; value: string }[]>(
    () => api.listProjectVariables(projectId),
    [projectId],
  )
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [form] = Form.useForm<VariableFormValues>()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (name: string, value: string) => {
    setEditing(name)
    form.setFieldsValue({ name, value })
    setModalOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      await api.putProjectVariable(projectId, values)
      message.success(editing ? '已更新 Variable' : '已创建 Variable')
      setModalOpen(false)
      variables.reload()
      onChanged?.()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const remove = async (name: string) => {
    try {
      await api.deleteProjectVariable(projectId, name)
      message.success('已删除 Variable')
      variables.reload()
      onChanged?.()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<{ name: string; value: string }> = [
    {
      title: '名称',
      dataIndex: 'name',
      render: (name: string) => <Typography.Text code>{name}</Typography.Text>,
    },
    {
      title: '值',
      dataIndex: 'value',
      render: (value: string) => <Typography.Text>{value}</Typography.Text>,
    },
    ...(canManage
      ? [
          {
            title: '操作',
            key: 'actions',
            width: 140,
            render: (_: unknown, record: { name: string; value: string }) => (
              <Space size={4}>
                <Button
                  type="link"
                  size="small"
                  onClick={() => openEdit(record.name, record.value)}
                >
                  编辑
                </Button>
                <Popconfirm
                  title={`删除 Variable「${record.name}」？`}
                  description="引用它的运行方案会在保存时因解析失败而报错，已有 Run 不受影响。"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => remove(record.name)}
                >
                  <Button type="link" size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          } satisfies ColumnsType<{ name: string; value: string }>[number],
        ]
      : []),
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        在运行方案的环境变量里用 <Typography.Text code>{'${{ vars.NAME }}'}</Typography.Text>{' '}
        引用；引用按 Project → Project Owner 顺序解析，结果由后端确认。
      </Typography.Paragraph>

      {canManage && (
        <div>
          <Button icon={<PlusOutlined />} onClick={openCreate}>
            新建 Variable
          </Button>
        </div>
      )}

      <AsyncSection
        loading={variables.loading}
        error={variables.error}
        empty={(variables.data ?? []).length === 0}
        emptyText="还没有 Project Variable。创建后可以在运行方案环境变量中引用。"
      >
        <Table
          rowKey="name"
          size="small"
          dataSource={variables.data ?? []}
          columns={columns}
          pagination={false}
        />
      </AsyncSection>

      <Modal
        title={editing ? `编辑 Variable「${editing}」` : '新建 Variable'}
        open={modalOpen}
        onOk={submit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请输入名称' },
              {
                pattern: /^[A-Za-z_][A-Za-z0-9_]*$/,
                message: '只能包含字母、数字和下划线，且不能以数字开头',
              },
            ]}
          >
            <Input placeholder="例如 DATASET_URL" disabled={editing !== null} />
          </Form.Item>
          <Form.Item name="value" label="值" rules={[{ required: true, message: '请输入值' }]}>
            <Input.TextArea autoSize placeholder="Variable 的值" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
