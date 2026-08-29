import { InfoIcon } from '@primer/octicons-react'
import { matchPath } from 'react-router-dom'

import styles from './AppShell.module.css'
import { contextGuideCopy } from './copy'

const contextGuides = [
  { pattern: '/', message: contextGuideCopy.home },
  { pattern: '/user-groups/:userGroupId/*', message: contextGuideCopy.userGroup },
  { pattern: '/environments', message: contextGuideCopy.environment },
  { pattern: '/environments/:environmentId', message: contextGuideCopy.environment },
  { pattern: '/environment-versions/:versionId', message: contextGuideCopy.environment },
  { pattern: '/projects/:projectId', message: contextGuideCopy.project },
  { pattern: '/versions/:versionId', message: contextGuideCopy.version },
  { pattern: '/runs/:runId', message: contextGuideCopy.run },
] as const

interface Props {
  pathname: string
}

export function ContextGuide({ pathname }: Props) {
  const guide = contextGuides.find(({ pattern }) => matchPath(pattern, pathname))
  if (!guide) return null

  return (
    <aside className={styles.contextGuide} aria-label={contextGuideCopy.ariaLabel}>
      <InfoIcon aria-hidden="true" />
      <span>{guide.message}</span>
    </aside>
  )
}
