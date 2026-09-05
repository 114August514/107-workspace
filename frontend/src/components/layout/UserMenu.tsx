import { ChevronDownIcon } from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Button,
  Dialog,
  FormControl,
  Stack,
  TextInput,
} from '@primer/react'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { User } from '../../api/types'
import { authCopy } from '../../auth/authCopy'

interface Props {
  user: User
}

export function UserMenu({ user }: Props) {
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)
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
            <ActionList.Item onSelect={() => setProfileOpen(true)}>
              {authCopy.profile}
            </ActionList.Item>
            <ActionList.Item
              onSelect={() => {
                navigate('/execution-context')
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
      {profileOpen ? <ProfileDialog user={user} onClose={() => setProfileOpen(false)} /> : null}
    </>
  )
}

function ProfileDialog({ user, onClose }: { user: User; onClose: () => void }) {
  return (
    <Dialog
      title={authCopy.profileTitle}
      onClose={onClose}
      footerButtons={[
        {
          content: authCopy.profileClose,
          buttonType: 'primary',
          onClick: onClose,
        },
      ]}
    >
      <Stack gap="normal">
        <FormControl>
          <FormControl.Label>{authCopy.profileDisplayName}</FormControl.Label>
          <TextInput value={user.display_name} readOnly block />
        </FormControl>
        <FormControl>
          <FormControl.Label>{authCopy.profileUsername}</FormControl.Label>
          <TextInput value={user.username} readOnly block />
        </FormControl>
        <FormControl>
          <FormControl.Label>{authCopy.profileEmail}</FormControl.Label>
          <TextInput
            value={user.email?.trim() ? user.email : authCopy.profileEmailMissing}
            readOnly
            block
          />
        </FormControl>
      </Stack>
    </Dialog>
  )
}
