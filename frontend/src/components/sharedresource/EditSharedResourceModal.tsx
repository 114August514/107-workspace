import { Form, Input, Modal, message } from 'antd'
import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type { SharedResource } from '../../api/types'

interface Props {
  open: boolean
  resource: SharedResource | undefined
  onClose: () => void
  onUpdated: () => void
}

export function EditSharedResourceModal({ open, resource, onClose, onUpdated }: Props) {
  const [form] = Form.useForm<{ name: string; description: string }>()
  const [submitting, setSubmitting] = useState(false)

  // 每次打开都把当前值回填进去——表单是受控的，不复位就会留着上一次的改动。
  useEffect(() => {
    if (open && resource) {
      form.setFieldsValue({ name: resource.name, description: resource.description })
    }
  }, [open, resource, form])

  const submit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await api.updateSharedResource(resource!.id, {
        name: values.name,
        description: values.description ?? '',
      })
      message.success('已保存修改')
      onUpdated()
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
      title="修改 Shared Resource"
      okText="保存"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" requiredMark="optional">
        <Form.Item name="name" label="名称" rules={[{ required: true, message: '请填写资源名称' }]}>
          <Input maxLength={128} />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea rows={3} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
