import { Button, Form, Input, Popconfirm, Space, Table, Tag, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { Member, MembershipRole, UserGroup } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'
import { roleLabel } from '../../utils/roles'
import { AsyncSection } from '../common/AsyncSection'
import { RoleTag } from '../common/RoleTag'

/**
 * Membership roles are static identity information in the table. The server
 * projects contextual governance capabilities for each target member.
 */

interface Props {
  userGroup: UserGroup
}

export function MemberPanel({ userGroup }: Props) {
  const members = useAsync<Member[]>(() => api.listMembers(userGroup.id), [userGroup.id])
  const [form] = Form.useForm<{ username: string }>()
  const [inviting, setInviting] = useState(false)
  const canInvite = can(userGroup, 'member.invite')
  const canGovernMembers = can(userGroup, 'member.remove') || can(userGroup, 'member.role.manage')

  const invite = async () => {
    const values = await form.validateFields()
    setInviting(true)
    try {
      await api.inviteMember(userGroup.id, values.username)
      message.success(`已向 ${values.username} 发送邀请`)
      form.resetFields()
      members.reload()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setInviting(false)
    }
  }

  const remove = async (member: Member) => {
    try {
      await api.removeMember(userGroup.id, member.user_id)
      message.success(`已移除 ${member.username}`)
      members.reload()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const changeRole = async (member: Member, role: MembershipRole) => {
    try {
      await api.changeMemberRole(userGroup.id, member.user_id, role)
      message.success(`${member.username} 的角色已改为 ${roleLabel(role)}`)
      members.reload()
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const columns: ColumnsType<Member> = [
    { title: '用户名', dataIndex: field<Member>('username') },
    { title: '显示名', dataIndex: field<Member>('display_name') },
    {
      title: '角色',
      dataIndex: field<Member>('role'),
      width: 160,
      render: (role: MembershipRole) => <RoleTag role={role} />,
    },
    {
      title: '状态',
      dataIndex: field<Member>('status'),
      width: 120,
      render: (status: string) =>
        status === 'active' ? <Tag color="green">已加入</Tag> : <Tag color="orange">待确认</Tag>,
    },
  ]

  if (canGovernMembers) {
    columns.push({
      title: '操作',
      width: 180,
      render: (_, member) => {
        const canChangeRole = can(member, 'member.role.manage')
        const canRemove = can(member, 'member.remove')
        if (!canChangeRole && !canRemove) return null
        return (
          <Space size="small">
            {canChangeRole && (
              <Button
                type="link"
                size="small"
                onClick={() => changeRole(member, member.role === 'admin' ? 'member' : 'admin')}
              >
                {member.role === 'admin' ? '设为普通成员' : '设为管理员'}
              </Button>
            )}
            {canRemove && (
              <Popconfirm
                title={`移除 ${member.username}？`}
                description="移除后该成员立刻失去这个 User Group 的访问权。"
                okText="移除"
                cancelText="取消"
                onConfirm={() => remove(member)}
              >
                <Button type="link" danger size="small">
                  移除
                </Button>
              </Popconfirm>
            )}
          </Space>
        )
      },
    })
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {canInvite && (
        <Form form={form} layout="inline">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请填写用户名' }]}
            style={{ minWidth: 220 }}
          >
            <Input placeholder="要邀请的用户名" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={invite} loading={inviting}>
              邀请成员
            </Button>
          </Form.Item>
        </Form>
      )}

      <AsyncSection loading={members.loading} error={members.error}>
        <Table
          rowKey="user_id"
          size="small"
          dataSource={members.data ?? []}
          columns={columns}
          pagination={false}
        />
      </AsyncSection>
    </Space>
  )
}
