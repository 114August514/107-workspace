// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ProjectLanguages as ProjectLanguagesData } from '../../src/api/types'
import { ProjectLanguages } from '../../src/components/project/ProjectLanguages'
import { PrimerRoot } from '../../src/primer/setup'

const statistics: ProjectLanguagesData = {
  total_code_lines: 200,
  languages: [
    { name: 'Python', code_lines: 150, percentage: 75 },
    { name: 'Shell', code_lines: 50, percentage: 25 },
  ],
}

function renderLanguages(overrides: Partial<Parameters<typeof ProjectLanguages>[0]> = {}) {
  const props = {
    statistics,
    loading: false,
    error: undefined,
    onRetry: vi.fn(),
    ...overrides,
  }
  render(
    <PrimerRoot>
      <ProjectLanguages {...props} />
    </PrimerRoot>,
  )
  return props
}

afterEach(cleanup)

describe('Project Languages', () => {
  it('renders a GitHub-style composition bar and legend for the latest Version statistics', () => {
    renderLanguages()

    const composition = screen.getByRole('img', {
      name: '最新 Project Version 的语言构成，共 200 行代码',
    })
    expect(within(composition).getByTitle('Python 75% · 150 行代码')).toHaveStyle({ width: '75%' })
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('Shell')).toBeInTheDocument()
    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('does not imply Working State statistics when no immutable Version has code', () => {
    renderLanguages({ statistics: { languages: [], total_code_lines: 0 } })

    expect(
      screen.getByText('保存包含代码的 Project Version 后，这里会显示语言构成。'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /语言构成/ })).not.toBeInTheDocument()
  })

  it('shows a retry action after loading fails', () => {
    const onRetry = vi.fn()
    renderLanguages({ statistics: undefined, error: new Error('offline'), onRetry })

    expect(screen.getByRole('alert')).toHaveTextContent('无法加载语言统计。')
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
