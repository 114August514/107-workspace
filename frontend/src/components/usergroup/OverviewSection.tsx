import { useOutletContext } from 'react-router-dom'

import { userGroupPageCopy as copy } from './userGroupCopy'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'

export function OverviewSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  return (
    <section aria-labelledby="user-group-overview-title">
      <h2 id="user-group-overview-title">{copy.sections.overview.title}</h2>
      <p>{userGroup.name}</p>
    </section>
  )
}
