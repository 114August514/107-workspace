import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ApiError } from '../../api/client'
import { AsyncSection } from './AsyncSection'

describe('AsyncSection', () => {
  it('加载完成后渲染内容', () => {
    render(
      <AsyncSection loading={false} error={undefined}>
        <p>内容</p>
      </AsyncSection>,
    )
    expect(screen.getByText('内容')).toBeInTheDocument()
  })

  it('空数据时显示提示而不是内容', () => {
    render(
      <AsyncSection loading={false} error={undefined} empty emptyText="还没有 Project">
        <p>内容</p>
      </AsyncSection>,
    )
    expect(screen.getByText('还没有 Project')).toBeInTheDocument()
    expect(screen.queryByText('内容')).not.toBeInTheDocument()
  })

  it('提交前检查失败时逐条列出问题', () => {
    const error = new ApiError(422, 'preflight_rejected', '提交前检查未通过', [
      'Project 还没有保存过版本',
      '没有可用的运行环境',
    ])
    render(
      <AsyncSection loading={false} error={error}>
        <p>内容</p>
      </AsyncSection>,
    )

    expect(screen.getByText('提交前检查未通过')).toBeInTheDocument()
    expect(screen.getByText('Project 还没有保存过版本')).toBeInTheDocument()
    expect(screen.getByText('没有可用的运行环境')).toBeInTheDocument()
  })
})
