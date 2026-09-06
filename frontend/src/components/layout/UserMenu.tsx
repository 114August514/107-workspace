import { ChevronDownIcon } from '@primer/octicons-react'
import { ActionList, ActionMenu, Button } from '@primer/react'
import { useRef } from 'react'
import { useNavigate } from 'react-router-dom'

import type { User } from '../../api/types'
import { authCopy } from '../../auth/authCopy'

interface Props {
  user: User
}

export function UserMenu({ user }: Props) {
  const navigate = useNavigate()
  const logoutFormRef = useRef<HTMLFormElement>(null)
  const displayName = user.display_name || user.username

  return (
    <>
      <ActionMenu>
        <ActionMenu.Anchor>
          <Button
            variant="invisible"
            trailingVisual={ChevronDownIcon}
            aria-label={authCopy.userMenu(displayName)}
          >
            {displayName}
          </Button>
        </ActionMenu.Anchor>
        <ActionMenu.Overlay>
          <ActionList>
            <ActionList.Item
              onSelect={() => {
                navigate('/profile')
              }}
            >
              {authCopy.profile}
            </ActionList.Item>
            <ActionList.Item
              onSelect={() => {
                navigate('/settings')
              }}
            >
              {authCopy.settings}
            </ActionList.Item>
            <ActionList.Item
              variant="danger"
              onSelect={() => {
                logoutFormRef.current?.submit()
              }}
            >
              {authCopy.logout}
            </ActionList.Item>
          </ActionList>
        </ActionMenu.Overlay>
      </ActionMenu>
      <form ref={logoutFormRef} method="post" action="/logout" hidden />
    </>
  )
}
