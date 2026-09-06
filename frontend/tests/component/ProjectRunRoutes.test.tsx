// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, useParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProductRoutes } from '../../src/App'

vi.mock('../../src/pages/ProjectPage', () => ({
  ProjectPage: () => <h1>Project 运行方案</h1>,
}))
vi.mock('../../src/pages/RunPage', () => ({
  RunPage: () => <h1>Run {useParams().runId}</h1>,
}))
const empty = { data: undefined, loading: false, error: undefined, reload: async () => {} }
afterEach(cleanup)

describe('Project Runs 路由', () => {
  it('运行方案固定路径不会被解释成 Run ID', () => {
    render(
      <MemoryRouter initialEntries={['/projects/p-1/runs/configurations']}>
        <ProductRoutes username="student" home={empty} project={empty} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Project 运行方案' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Run configurations' })).toBeNull()
  })
  it('具体 Run 仍然进入运行结果页', () => {
    render(
      <MemoryRouter initialEntries={['/projects/p-1/runs/run-1']}>
        <ProductRoutes username="student" home={empty} project={empty} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Run run-1' })).toBeVisible()
  })
})
