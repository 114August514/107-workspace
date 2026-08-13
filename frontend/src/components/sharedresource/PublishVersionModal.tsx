import { Form, Input, Modal, Upload, message } from 'antd'
import type { UploadFile } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { useState } from 'react'

import { api } from '../../api/client'
import type { SharedResourceVersion } from '../../api/types'

interface Props {
  open: boolean
  resourceId: string
  onClose: () => void
  onPublished: (version: SharedResourceVersion) => void
}

const { Dragger } = Upload

export function PublishVersionModal({ open, resourceId, onClose, onPublished }: Props) {
  const [form] = Form.useForm<{ description: string; prefix: string }>()
  const [files, setFiles] = useState<UploadFile[]>([])
  const [submitting, setSubmitting] = useState(false)

  // beforeUpload 返回 false 阻止 antd 自动上传——我们要手动走 FormData，
  // 这样能带上 X-User 身份头并拿到结构化的错误信封。
  const beforeUpload = (file: File): false => {
    setFiles((current) => [...current, file as unknown as UploadFile])
    return false
  }

  const onRemove = (file: UploadFile) => {
    setFiles((current) => current.filter((item) => item.uid !== file.uid))
    return true
  }

  const submit = async () => {
    const values = await form.validateFields()
    if (files.length === 0) {
      message.error('请至少选择一个文件')
      return
    }
    setSubmitting(true)
    try {
      const version = await api.publishSharedResourceVersion(resourceId, {
        files: files as unknown as File[],
        description: values.description ?? '',
        prefix: values.prefix || undefined,
      })
      message.success(`已发布版本 ${version.label}`)
      form.resetFields()
      setFiles([])
      onPublished(version)
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
      title="发布新版本"
      okText="发布"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
      width={560}
    >
      <Form form={form} layout="vertical" requiredMark="optional">
        <Form.Item label="文件" required>
          <Dragger fileList={files} multiple beforeUpload={beforeUpload} onRemove={onRemove}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此处</p>
            <p className="ant-upload-hint">
              支持多选。同名路径会导致版本发布失败，必要时用下面的前缀区分。
            </p>
          </Dragger>
        </Form.Item>
        <Form.Item name="prefix" label="路径前缀" extra="可选。文件会写入 prefix/<文件名>。">
          <Input placeholder="例如：data/" maxLength={128} />
        </Form.Item>
        <Form.Item name="description" label="版本说明">
          <Input.TextArea rows={3} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
