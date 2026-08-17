import { Button, Card, Tag } from 'antd'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { UserGroup } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncSection } from '../components/common/AsyncSection'
import { RoleTag } from '../components/common/RoleTag'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { MemberPanel } from '../components/workspace/MemberPanel'

/** User Group identity and Membership governance only. */
export function UserGroupPage() {
  const { userGroupId = '' } = useParams()
  const userGroup = useAsync<UserGroup>(() => api.getUserGroup(userGroupId), [userGroupId])

  return (
    <Stack gap="large">
      <AsyncSection loading={userGroup.loading} error={userGroup.error}>
        {userGroup.data && (
          <PageHeader
            breadcrumb={[{ title: <Link to="/">首页</Link> }, { title: userGroup.data.name }]}
            title={userGroup.data.name}
            tags={
              <>
                <Tag color="blue">User Group</Tag>
                <RoleTag role={userGroup.data.role} />
              </>
            }
            description={userGroup.data.description || '这个 User Group 还没有填写说明'}
            actions={
              <Link to={`/workspaces/${userGroupId}`}>
                <Button>旧 Workspace 兼容视图</Button>
              </Link>
            }
          />
        )}
      </AsyncSection>

      <Card title="成员">{userGroup.data && <MemberPanel userGroup={userGroup.data} />}</Card>
    </Stack>
  )
}
