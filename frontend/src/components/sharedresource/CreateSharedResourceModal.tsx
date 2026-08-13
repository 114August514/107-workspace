import { Form, Input, Modal, message } from 'antd'
import { useState } from 'react'

import { api } from '../../api/client'
import type { SharedResource } from '../../api/types'

interface Props {
  open: boolean
  workspaceId: string
  onClose: () => void
  onCreated: (resource: SharedResource) => void
}

export function CreateSharedResourceModal({ open, workspaceId, onClose, onCreated }: Props) {
  const [form] = Form.useForm<{ name: string; description: string }>()
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const resource = await api.createSharedResource(
        workspaceId,
        values.name,
        values.description ?? '',
      )
      message.success(`已创建 Shared Resource「${resource.name}」`)
      form.resetFields()
      onCreated(resource)
      onClose()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      title="创建 Shared Resource"
      okText="创建"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" requiredMark="optional">
        <Form.Item name="name" label="名称" rules={[{ required: true, message: '请填写资源名称' }]}>
          <Input placeholder="例如：预训练权重" maxLength={128} />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea rows={3} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
