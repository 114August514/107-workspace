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

interface SecretFormValues {
  name: string
  value: string
}

/**
 * Project Secret 管理（Issue #54）。
 *
 * Secret 只能写入和轮换，不能回读：列表只展示名字，表单值输入后即提交，
 * 不在前端保存或回显明文。
 */
export function ProjectSecretsPanel({ projectId, access, onChanged }: Props) {
  const canManage = can(access, 'config.manage')
  const secrets = useAsync<string[]>(() => api.listProjectSecrets(projectId), [projectId])
  const [modalOpen, setModalOpen] = useState(false)
  const [replacing, setReplacing] = useState<string | null>(null)
  const [form] = Form.useForm<SecretFormValues>()

  const openCreate = () => {
    setReplacing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openReplace = (name: string) => {
    setReplacing(name)
    form.setFieldsValue({ name, value: '' })
    setModalOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      await api.putProjectSecret(projectId, values)
      message.success(replacing ? `已替换 Secret「${values.name}」的值` : '已创建 Secret')
      setModalOpen(false)
      secrets.reload()
      onChanged?.()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const remove = async (name: string) => {
    try {
      await api.deleteProjectSecret(projectId, name)
      message.success('已删除 Secret')
      secrets.reload()
      onChanged?.()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<string> = [
    {
      title: '名称',
      dataIndex: '',
      render: (name: string) => <Typography.Text code>{name}</Typography.Text>,
    },
    ...(canManage
      ? [
          {
            title: '操作',
            key: 'actions',
            width: 160,
            render: (_: unknown, name: string) => (
              <Space size={4}>
                <Button type="link" size="small" onClick={() => openReplace(name)}>
                  替换值
                </Button>
                <Popconfirm
                  title={`删除 Secret「${name}」？`}
                  description="引用它的 Run 会在 Preflight 中明确失败，不会被替换为空值；已有 Run 不受影响。"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => remove(name)}
                >
                  <Button type="link" size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          } satisfies ColumnsType<string>[number],
        ]
      : []),
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        在运行方案环境变量里用 <Typography.Text code>{'${{ secrets.NAME }}'}</Typography.Text>{' '}
        引用；值只在写入时可见，保存后不能回读，列表只展示名字。
      </Typography.Paragraph>

      {canManage && (
        <div>
          <Button icon={<PlusOutlined />} onClick={openCreate}>
            新建 Secret
          </Button>
        </div>
      )}

      <AsyncSection
        loading={secrets.loading}
        error={secrets.error}
        empty={(secrets.data ?? []).length === 0}
        emptyText="还没有 Project Secret。创建后可以在运行方案环境变量中引用。"
      >
        <Table
          rowKey={(name) => name}
          size="small"
          dataSource={secrets.data ?? []}
          columns={columns}
          pagination={false}
        />
      </AsyncSection>

      <Modal
        title={replacing ? `替换 Secret「${replacing}」的值` : '新建 Secret'}
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
            <Input placeholder="例如 HF_TOKEN" disabled={replacing !== null} />
          </Form.Item>
          <Form.Item
            name="value"
            label={replacing ? '新值' : '值'}
            rules={[{ required: true, message: '请输入值；保存后不能回读' }]}
          >
            <Input.Password
              autoComplete="new-password"
              placeholder={replacing ? '输入替换后的值' : 'Secret 的值'}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
