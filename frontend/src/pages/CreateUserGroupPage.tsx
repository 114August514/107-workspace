import { useNavigate } from 'react-router-dom'

import { CreateUserGroupForm } from '../components/workspace/CreateUserGroupDialog'
import type { UserGroup } from '../api/types'

export function CreateUserGroupPage() {
  const navigate = useNavigate()
  const handleCreated = (userGroup: UserGroup) => {
    navigate(`/user-groups/${userGroup.id}`)
  }
  return <CreateUserGroupForm page onClose={() => navigate('/')} onCreated={handleCreated} />
}
