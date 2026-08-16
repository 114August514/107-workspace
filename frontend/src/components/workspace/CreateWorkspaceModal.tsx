import { Form, Input, Modal, message } from 'antd'
import { useState } from 'react'

import { api } from '../../api/client'
import type { UserGroup } from '../../api/types'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (userGroup: UserGroup) => void
}

interface FormValues {
  name: string
  description: string
}

export function CreateWorkspaceModal({ open, onClose, onCreated }: Props) {
  const [form] = Form.useForm<FormValues>()
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const userGroup = await api.createUserGroup(values.name, values.description ?? '')
      message.success(`已创建 User Group「${userGroup.name}」`)
      form.resetFields()
      onCreated(userGroup)
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
      title="创建 User Group"
      okText="创建"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" requiredMark="optional">
        <Form.Item
          name="name"
          label="名称"
          rules={[{ required: true, message: '请填写 User Group 名称' }]}
        >
          <Input placeholder="例如：计算物理课题组" maxLength={128} />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea rows={3} placeholder="这个 User Group 用来做什么" maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
