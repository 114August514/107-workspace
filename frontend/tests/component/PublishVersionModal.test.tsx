// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type {
  SharedResourcePublicationAttempt,
  SharedResourceVersionDetail,
} from '../../src/api/types'
import { PublishVersionModal } from '../../src/components/sharedresource/PublishVersionModal'

const pending: SharedResourcePublicationAttempt = {
  id: 'shrpa_1',
  shared_resource_id: 'shr_1',
  status: 'pending',
  description: 'candidate',
  file_count: 1,
  total_size: 7,
  validation_summary: '等待校验候选内容',
  failure_reason: null,
  version_id: null,
  created_by: 'usr_alice',
  created_at: '2026-08-24T00:00:00Z',
  started_at: null,
  finished_at: null,
}

const version: SharedResourceVersionDetail = {
  id: 'shrv_1',
  shared_resource_id: 'shr_1',
  sequence: 1,
  label: 'v1',
  description: 'candidate',
  file_count: 1,
  total_size: 7,
  manifest_hash: 'a'.repeat(64),
  validation_summary: '已校验 1 个文件，共 7 字节；内容哈希与大小一致',
  created_by: 'usr_alice',
  created_at: '2026-08-24T00:00:01Z',
  files: [{ path: 'data.txt', size: 7, content_hash: 'b'.repeat(64) }],
}

function chooseFileAndPublish(onPublished = vi.fn()) {
  render(
    <PublishVersionModal open resourceId="shr_1" onClose={vi.fn()} onPublished={onPublished} />,
  )
  fireEvent.change(screen.getByLabelText('文件'), {
    target: { files: [new File(['payload'], 'data.txt', { type: 'text/plain' })] },
  })
  fireEvent.click(screen.getByRole('button', { name: '发布版本' }))
  return onPublished
}

describe('PublishVersionModal publication attempts', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    window.sessionStorage.clear()
  })

  it('keeps pending visible and publishes only after processor success', async () => {
    vi.spyOn(api, 'createSharedResourcePublicationAttempt').mockResolvedValue(pending)
    vi.spyOn(api, 'getSharedResourcePublicationAttempt')
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce({
        ...pending,
        status: 'succeeded',
        version_id: version.id,
        validation_summary: version.validation_summary,
        started_at: '2026-08-24T00:00:00Z',
        finished_at: '2026-08-24T00:00:01Z',
      })
    vi.spyOn(api, 'getSharedResourceVersion').mockResolvedValue(version)
    const onPublished = chooseFileAndPublish()

    expect(await screen.findByText('等待校验候选内容')).toBeInTheDocument()
    await waitFor(() => expect(onPublished).toHaveBeenCalledWith(version), { timeout: 1500 })
  })

  it('shows durable validation failure without claiming a version was published', async () => {
    vi.spyOn(api, 'createSharedResourcePublicationAttempt').mockResolvedValue(pending)
    vi.spyOn(api, 'getSharedResourcePublicationAttempt').mockResolvedValue({
      ...pending,
      status: 'failed',
      validation_summary: '候选内容校验失败',
      failure_reason: '文件 data.txt 的候选内容不存在',
      started_at: '2026-08-24T00:00:00Z',
      finished_at: '2026-08-24T00:00:01Z',
    })
    const getVersion = vi.spyOn(api, 'getSharedResourceVersion')
    const onPublished = chooseFileAndPublish()

    expect(await screen.findByText('文件 data.txt 的候选内容不存在')).toBeInTheDocument()
    expect(getVersion).not.toHaveBeenCalled()
    expect(onPublished).not.toHaveBeenCalled()
  })

  it('stops scheduled and in-flight result reads when closed while pending', async () => {
    vi.spyOn(api, 'createSharedResourcePublicationAttempt').mockResolvedValue(pending)
    const getAttempt = vi
      .spyOn(api, 'getSharedResourcePublicationAttempt')
      .mockResolvedValue(pending)
    const onClose = vi.fn()
    render(<PublishVersionModal open resourceId="shr_1" onClose={onClose} onPublished={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('文件'), {
      target: { files: [new File(['payload'], 'data.txt', { type: 'text/plain' })] },
    })
    fireEvent.click(screen.getByRole('button', { name: '发布版本' }))

    expect(await screen.findByText('等待校验候选内容')).toBeInTheDocument()
    await waitFor(() => expect(getAttempt).toHaveBeenCalledTimes(1))
    const signal = getAttempt.mock.calls[0]?.[1]
    fireEvent.click(screen.getByRole('button', { name: '取消' }))

    expect(onClose).toHaveBeenCalledOnce()
    expect(signal?.aborted).toBe(true)
    await new Promise((resolve) => window.setTimeout(resolve, 600))
    expect(getAttempt).toHaveBeenCalledTimes(1)
  })

  it('resumes a retained durable attempt after unmount without uploading again', async () => {
    const createAttempt = vi
      .spyOn(api, 'createSharedResourcePublicationAttempt')
      .mockResolvedValue(pending)
    const getAttempt = vi
      .spyOn(api, 'getSharedResourcePublicationAttempt')
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce({
        ...pending,
        status: 'succeeded',
        version_id: version.id,
        validation_summary: version.validation_summary,
        started_at: '2026-08-24T00:00:00Z',
        finished_at: '2026-08-24T00:00:01Z',
      })
    vi.spyOn(api, 'getSharedResourceVersion').mockResolvedValue(version)
    const onPublished = vi.fn()
    const firstView = render(
      <PublishVersionModal open resourceId="shr_1" onClose={vi.fn()} onPublished={onPublished} />,
    )
    fireEvent.change(screen.getByLabelText('文件'), {
      target: { files: [new File(['payload'], 'data.txt', { type: 'text/plain' })] },
    })
    fireEvent.click(screen.getByRole('button', { name: '发布版本' }))
    expect(await screen.findByText('等待校验候选内容')).toBeInTheDocument()
    await waitFor(() => expect(getAttempt).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    firstView.unmount()

    expect(window.sessionStorage.getItem('shared-resource-publication-attempt:shr_1')).toBe(
      pending.id,
    )
    render(
      <PublishVersionModal open resourceId="shr_1" onClose={vi.fn()} onPublished={onPublished} />,
    )
    expect(screen.getByRole('button', { name: '继续查询结果' })).toBeEnabled()
    expect(createAttempt).toHaveBeenCalledTimes(1)
    expect(getAttempt).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: '继续查询结果' }))
    await waitFor(() => expect(onPublished).toHaveBeenCalledWith(version))
    expect(createAttempt).toHaveBeenCalledTimes(1)
    expect(window.sessionStorage.getItem('shared-resource-publication-attempt:shr_1')).toBeNull()
  })

  it('keeps retained attempts isolated when navigation changes resourceId', async () => {
    const attemptA = { ...pending, id: 'shrpa_a', shared_resource_id: 'shr_a' }
    const attemptB = { ...pending, id: 'shrpa_b', shared_resource_id: 'shr_b' }
    window.sessionStorage.setItem('shared-resource-publication-attempt:shr_a', attemptA.id)
    window.sessionStorage.setItem('shared-resource-publication-attempt:shr_b', attemptB.id)
    const createAttempt = vi.spyOn(api, 'createSharedResourcePublicationAttempt')
    const getAttempt = vi
      .spyOn(api, 'getSharedResourcePublicationAttempt')
      .mockImplementation(async (attemptId) => {
        if (attemptId === attemptB.id) {
          return {
            ...attemptB,
            status: 'failed',
            validation_summary: 'B 候选内容校验失败',
            failure_reason: 'B 候选内容不存在',
            started_at: '2026-08-24T00:00:00Z',
            finished_at: '2026-08-24T00:00:01Z',
          }
        }
        return attemptA
      })
    const view = render(
      <PublishVersionModal open resourceId="shr_a" onClose={vi.fn()} onPublished={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: '继续查询结果' }))
    await waitFor(() =>
      expect(getAttempt).toHaveBeenCalledWith(attemptA.id, expect.any(AbortSignal)),
    )
    view.rerender(
      <PublishVersionModal open resourceId="shr_b" onClose={vi.fn()} onPublished={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: '继续查询结果' }))
    expect(await screen.findByText('B 候选内容不存在')).toBeInTheDocument()

    expect(getAttempt.mock.calls.map(([attemptId]) => attemptId)).toEqual([
      attemptA.id,
      attemptB.id,
    ])
    expect(window.sessionStorage.getItem('shared-resource-publication-attempt:shr_a')).toBe(
      attemptA.id,
    )
    expect(window.sessionStorage.getItem('shared-resource-publication-attempt:shr_b')).toBeNull()
    await new Promise((resolve) => window.setTimeout(resolve, 600))
    expect(getAttempt).toHaveBeenCalledTimes(2)

    view.rerender(
      <PublishVersionModal open resourceId="shr_a" onClose={vi.fn()} onPublished={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: '继续查询结果' }))
    await waitFor(() => expect(getAttempt).toHaveBeenCalledTimes(3))
    expect(getAttempt.mock.calls[2]?.[0]).toBe(attemptA.id)
    expect(createAttempt).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
  })
})
