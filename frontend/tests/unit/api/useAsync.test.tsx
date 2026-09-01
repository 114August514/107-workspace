// @vitest-environment jsdom

import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useAsync, usePolling } from '../../../src/api/useAsync'

describe('useAsync latest-wins', () => {
  it('ignores an older request resolving after reload', async () => {
    let resolveA!: (value: string) => void
    let resolveB!: (value: string) => void
    const loader = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<string>((resolve) => {
            resolveA = resolve
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<string>((resolve) => {
            resolveB = resolve
          }),
      )
    const { result } = renderHook(() => useAsync(loader, []))
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(1))
    let latest!: Promise<void>
    act(() => {
      latest = result.current.reload()
    })
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(2))
    await act(async () => {
      resolveB('new')
      await latest
    })
    expect(result.current.data).toBe('new')
    act(() => resolveA('old'))
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(result.current.data).toBe('new')
    expect(result.current.loading).toBe(false)
  })

  it('ignores an older request rejecting after the latest succeeds', async () => {
    let rejectA!: (error: Error) => void
    let resolveB!: (value: string) => void
    const loader = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<string>((_, reject) => {
            rejectA = reject
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<string>((resolve) => {
            resolveB = resolve
          }),
      )
    const { result } = renderHook(() => useAsync(loader, []))
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(1))
    let latest!: Promise<void>
    act(() => {
      latest = result.current.reload()
    })
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(2))
    await act(async () => {
      resolveB('new')
      await latest
    })
    expect(result.current.data).toBe('new')
    act(() => rejectA(new Error('old failure')))
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(result.current.data).toBe('new')
    expect(result.current.error).toBeUndefined()
    expect(result.current.loading).toBe(false)
  })
})

describe('useAsync silent reload', () => {
  it('keeps existing data visible and resolves after the background request completes', async () => {
    let resolveRefresh!: (value: string) => void
    const loader = vi
      .fn()
      .mockResolvedValueOnce('old')
      .mockImplementationOnce(
        () =>
          new Promise<string>((resolve) => {
            resolveRefresh = resolve
          }),
      )
    const { result } = renderHook(() => useAsync(loader, []))
    await waitFor(() => expect(result.current.data).toBe('old'))

    let refresh!: Promise<void>
    act(() => {
      refresh = result.current.reload({ silent: true })
    })
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(2))

    expect(refresh).toBeInstanceOf(Promise)
    expect(result.current.data).toBe('old')
    expect(result.current.loading).toBe(false)

    await act(async () => {
      resolveRefresh('new')
      await refresh
    })
    expect(result.current.data).toBe('new')
  })

  it('retains usable data when a silent refresh fails', async () => {
    const loader = vi.fn().mockResolvedValueOnce('old').mockRejectedValueOnce(new Error('offline'))
    const { result } = renderHook(() => useAsync(loader, []))
    await waitFor(() => expect(result.current.data).toBe('old'))

    await act(async () => {
      await result.current.reload({ silent: true })
    })

    expect(result.current.data).toBe('old')
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeUndefined()
  })
})

describe('usePolling sequencing', () => {
  it('waits for each callback and a full interval before starting the next poll', async () => {
    vi.useFakeTimers()
    try {
      let resolveFirst!: () => void
      const callback = vi
        .fn()
        .mockImplementationOnce(
          () =>
            new Promise<void>((resolve) => {
              resolveFirst = resolve
            }),
        )
        .mockResolvedValue(undefined)
      const { unmount } = renderHook(() => usePolling(callback, 2_000, true))

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000)
      })
      expect(callback).toHaveBeenCalledTimes(1)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(6_000)
      })
      expect(callback).toHaveBeenCalledTimes(1)

      await act(async () => {
        resolveFirst()
        await Promise.resolve()
        await vi.advanceTimersByTimeAsync(1_999)
      })
      expect(callback).toHaveBeenCalledTimes(1)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1)
      })
      expect(callback).toHaveBeenCalledTimes(2)
      unmount()
    } finally {
      vi.useRealTimers()
    }
  })
})
