import type { Run, RunConfiguration } from '../../api/types'
import { RunSubmissionDialog } from './RunSubmissionDialog'

interface Props {
  open: boolean
  projectId: string
  configuration: RunConfiguration | null
  onClose: () => void
  onSubmitted: (run: Run) => void
}
export function SubmitRunModal({ open, ...props }: Props) {
  return open && props.configuration ? (
    <RunSubmissionDialog key={`${props.projectId}:${props.configuration.id}`} {...props} />
  ) : null
}
