import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import type { RunDetail } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'

/** Resolve notification/deep links that only carry a Run ID into the canonical Project route. */
export function RunLocatorPage() {
  const { runId = '' } = useParams()
  const navigate = useNavigate()
  const detail = useAsync<RunDetail>(() => api.getRun(runId), [runId])
  const error = toAsyncError(detail.error)

  useEffect(() => {
    if (!detail.data) return
    navigate(`/projects/${detail.data.run.project_id}/runs/${detail.data.run.id}`, {
      replace: true,
    })
  }, [detail.data, navigate])

  return (
    <AsyncState
      loading={detail.loading || detail.data !== undefined}
      loadingText="正在打开 Run…"
      error={error ? { ...error, message: '无法打开这个 Run。' } : undefined}
      onRetry={detail.reload}
    >
      {null}
    </AsyncState>
  )
}
