import { Button, Form, Input, Popconfirm, Select, Space, Table, Tag, message } from 'antd'
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
 * 可以指派的角色。
 *
 * Owner 不在其中：换所有者是一次明确的交接，走转让流程，
 * 不能靠改角色造出第二个所有者。
 */
const ASSIGNABLE_ROLES = ['admin', 'member'] as const satisfies readonly MembershipRole[]

interface Props {
  userGroup: UserGroup
}

export function MemberPanel({ userGroup }: Props) {
  const members = useAsync<Member[]>(() => api.listMembers(userGroup.id), [userGroup.id])
  const [form] = Form.useForm<{ username: string; role: MembershipRole }>()
  const [inviting, setInviting] = useState(false)
  const canManage = can(userGroup, 'member.manage')

  const invite = async () => {
    const values = await form.validateFields()
    setInviting(true)
    try {
      await api.inviteMember(userGroup.id, values.username, values.role ?? 'member')
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
      render: (role: MembershipRole, member) => {
        if (!canManage || role === 'owner') {
          return <RoleTag role={role} />
        }
        return (
          <Select
            size="small"
            value={role}
            style={{ width: 120 }}
            onChange={(next) => changeRole(member, next)}
            options={ASSIGNABLE_ROLES.map((value) => ({
              value,
              label: roleLabel(value),
            }))}
          />
        )
      },
    },
    {
      title: '状态',
      dataIndex: field<Member>('status'),
      width: 120,
      render: (status: string) =>
        status === 'active' ? <Tag color="green">已加入</Tag> : <Tag color="orange">待确认</Tag>,
    },
  ]

  if (canManage) {
    columns.push({
      title: '操作',
      width: 100,
      render: (_, member) =>
        member.role === 'owner' ? null : (
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
        ),
    })
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {canManage && (
        <Form form={form} layout="inline" initialValues={{ role: 'member' }}>
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请填写用户名' }]}
            style={{ minWidth: 220 }}
          >
            <Input placeholder="要邀请的用户名" />
          </Form.Item>
          <Form.Item name="role">
            <Select
              style={{ width: 120 }}
              options={ASSIGNABLE_ROLES.map((value) => ({
                value,
                label: roleLabel(value),
              }))}
            />
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
