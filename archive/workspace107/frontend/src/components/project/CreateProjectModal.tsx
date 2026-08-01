import { Form, Input, Modal, message } from 'antd'
import { useState } from 'react'

import { api } from '../../api/client'
import type { Project } from '../../api/types'

interface Props {
  open: boolean
  workspaceId: string
  onClose: () => void
  onCreated: (project: Project) => void
}

export function CreateProjectModal({ open, workspaceId, onClose, onCreated }: Props) {
  const [form] = Form.useForm<{ name: string; description: string }>()
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const project = await api.createProject(workspaceId, values.name, values.description ?? '')
      message.success(`已创建 Project「${project.name}」`)
      form.resetFields()
      onCreated(project)
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
      title="创建 Project"
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
          rules={[{ required: true, message: '请填写 Project 名称' }]}
        >
          <Input placeholder="例如：第一个训练任务" maxLength={128} />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea rows={3} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
