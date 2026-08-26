import { Alert, Form, Input, Modal, Select, Typography, message } from 'antd'
import { useEffect } from 'react'

import { api } from '../../api/client'
import type { Project, ProjectVersion, UserGroup } from '../../api/types'
import { useAsync } from '../../api/useAsync'

interface Props {
  open: boolean
  version: ProjectVersion | null
  sourceProjectName: string
  onClose: () => void
  onForked: (project: Project) => void
}

/**
 * 从一个确定版本派生新 Project。
 *
 * 目标 User Group 列表只列**能建 Project 的**项。列出全部再让用户撞 403，
 * 等于把「你有没有权限」这个问题推给用户去试——而他试之前根本没法知道。
 */
export function ForkModal({ open, version, sourceProjectName, onClose, onForked }: Props) {
  const [form] = Form.useForm<{ target_owner_id: string; name: string; description: string }>()
  // Every returned User Group is an active Membership; current role capabilities permit
  // Project creation, while the backend remains authoritative for the exact request.
  const writableGroups = useAsync<UserGroup[]>(() => api.listUserGroups(), [open])

  useEffect(() => {
    if (open) {
      form.setFieldsValue({ name: sourceProjectName, description: '' })
    }
  }, [open, sourceProjectName, form])

  const submit = async () => {
    if (!version) return
    const values = await form.validateFields()
    try {
      const project = await api.forkVersion(version.id, {
        target_owner: { kind: 'user_group', id: values.target_owner_id },
        name: values.name,
        description: values.description,
      })
      message.success(`已创建 ${project.name}`)
      onForked(project)
      onClose()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  return (
    <Modal
      title={version ? `从 ${version.label} 派生新 Project` : 'Fork'}
      open={open}
      onCancel={onClose}
      onOk={submit}
      okText="创建"
      cancelText="取消"
      destroyOnHidden
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="复制的是内容和运行方案，不是权限"
        description="资源权益、成员权限、Secret 的值和 Run 历史都不会跟过去。运行方案里的 Secret 引用会一起复制，但需要你在目标 User Group 配置同名 Secret 才能跑起来。"
      />
      {writableGroups.error && (
        <Alert
          type="error"
          showIcon
          message="无法加载可创建 Project 的 User Group"
          description={writableGroups.error.message}
        />
      )}
      <Form form={form} layout="vertical">
        <Form.Item
          name="target_owner_id"
          label="创建到哪个 User Group"
          rules={[{ required: true, message: '请选择目标 User Group' }]}
        >
          <Select
            loading={writableGroups.loading}
            disabled={Boolean(writableGroups.error)}
            placeholder="选择一个你能建 Project 的 User Group"
            options={(writableGroups.data ?? []).map((group) => ({
              value: group.id,
              label: group.name,
            }))}
          />
        </Form.Item>
        <Form.Item
          name="name"
          label="新 Project 名称"
          rules={[{ required: true, message: '请填写名称' }]}
        >
          <Input placeholder={sourceProjectName} />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea rows={2} placeholder="可选" />
        </Form.Item>
      </Form>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        派生之后两边互不影响：源项目后续的修改不会同步过来，你的修改也不会回到源项目。
      </Typography.Text>
    </Modal>
  )
}
