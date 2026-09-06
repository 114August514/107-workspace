import type { Run } from '../../api/types'
import { RunSubmissionDialog } from './RunSubmissionDialog'

interface Props {
  open: boolean
  projectId: string
  versionId: string
  versionLabel: string
  defaultRunConfigurationId: string | null
  onClose: () => void
  onSubmitted: (run: Run) => void
}
export function RunFromVersionModal({ open, ...props }: Props) {
  return open ? (
    <RunSubmissionDialog key={`${props.projectId}:${props.versionId}`} {...props} />
  ) : null
}
