import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { RunStatus } from '../../api/types'
import { RunStatusTag } from './RunStatusTag'

describe('RunStatusTag', () => {
  const cases: Array<[RunStatus, string]> = [
    ['queued', '排队中'],
    ['running', '运行中'],
    ['succeeded', '成功'],
    ['failed', '失败'],
    ['cancelled', '已取消'],
    ['submit_failed', '提交失败'],
  ]

  it.each(cases)('%s 显示为「%s」', (status, label) => {
    render(<RunStatusTag status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
