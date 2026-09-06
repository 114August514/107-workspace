// @vitest-environment jsdom

import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { ReadmePanel } from '../../src/components/project/ReadmePanel'

describe('ReadmePanel', () => {
  afterEach(cleanup)

  it('separates panel chrome from GitHub-flavored Markdown content', () => {
    render(
      <MemoryRouter>
        <ReadmePanel
          content={'# 训练任务\n\n| 阶段 | 状态 |\n| --- | --- |\n| 准备 | 完成 |'}
          fileHref="/projects/project-1/files/file/README.md"
        />
      </MemoryRouter>,
    )

    const panel = screen.getByRole('region', { name: 'README.md' })
    expect(within(panel).getByRole('link', { name: '查看 README.md 文件' })).toHaveAttribute(
      'href',
      '/projects/project-1/files/file/README.md',
    )
    expect(within(panel).getByRole('heading', { name: '训练任务' })).toBeVisible()
    expect(within(panel).getByRole('table')).toBeVisible()
  })
})
